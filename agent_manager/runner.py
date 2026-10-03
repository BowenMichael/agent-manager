import asyncio
import os
import subprocess
import time
import uuid
import logging
from typing import Dict, Optional, Set, Any
from pathlib import Path

from fastapi import WebSocket
from agent_manager.config import (
    WORKSPACE_BASE, DEFAULT_REPO, DEFAULT_MODEL,
    GITHUB_PERSONAL_ACCESS_TOKEN, GEMINI_API_KEY
)
from agent_manager.models import (
    AgentSessionInfo, AgentStatus, MessageRole,
    ConversationMessage, SpawnRequest
)

logger = logging.getLogger("agent_manager.runner")

class AgentRunnerManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentRunnerManager, cls).__new__(cls)
            cls._instance.sessions: Dict[str, AgentSessionInfo] = {}
            cls._instance._tasks: Dict[str, asyncio.Task] = {}
            cls._instance._context_queues: Dict[str, asyncio.Queue] = {}
            cls._instance._active_agents: Dict[str, Any] = {}
            cls._instance._ws_subscribers: Set[WebSocket] = set()
        return cls._instance

    def register_ws(self, ws: WebSocket):
        self._ws_subscribers.add(ws)

    def unregister_ws(self, ws: WebSocket):
        self._ws_subscribers.discard(ws)

    async def broadcast(self, event_type: str, data: Any):
        payload = {"type": event_type, "data": data}
        dead_sockets = set()
        for ws in list(self._ws_subscribers):
            try:
                await ws.send_json(payload)
            except Exception:
                dead_sockets.add(ws)
        for dead in dead_sockets:
            self._ws_subscribers.discard(dead)

    def list_sessions(self) -> list[AgentSessionInfo]:
        return list(self.sessions.values())

    def get_session(self, session_id: str) -> Optional[AgentSessionInfo]:
        return self.sessions.get(session_id)

    def _setup_worktree(self, repo: str, issue_number: int) -> tuple[Optional[str], Optional[str]]:
        """Sets up isolated git worktree for the issue to prevent branch conflicts."""
        repo_name = repo.split("/")[-1]
        candidate_dirs = [
            WORKSPACE_BASE / repo_name,
            WORKSPACE_BASE / "F1 Front End" / repo_name,
            Path("e:/~Michael Bowen/Projects/F1 Front End/f1-frontend"),
            Path.cwd()
        ]
        repo_dir = None
        for cand in candidate_dirs:
            if cand.exists() and (cand / ".git").exists():
                repo_dir = cand
                break

        if not repo_dir:
            logger.warning(f"No git repository found for {repo}. Operating without isolated worktree.")
            return None, None

        worktrees_dir = repo_dir / ".worktrees"
        worktrees_dir.mkdir(parents=True, exist_ok=True)
        worktree_path = worktrees_dir / f"issue-{issue_number}"
        branch_name = f"feat/issue-{issue_number}"

        try:
            if not worktree_path.exists():
                cmd = f'git worktree add -B "{branch_name}" "{worktree_path}" origin/main'
                res = subprocess.run(cmd, cwd=str(repo_dir), shell=True, capture_output=True, text=True)
                if res.returncode != 0:
                    cmd_fallback = f'git worktree add -B "{branch_name}" "{worktree_path}" HEAD'
                    subprocess.run(cmd_fallback, cwd=str(repo_dir), shell=True, capture_output=True, text=True)
            return str(worktree_path), branch_name
        except Exception as e:
            logger.error(f"Failed to create worktree: {e}")
            return None, None

    async def spawn_agent(self, req: SpawnRequest) -> AgentSessionInfo:
        repo = req.repo or DEFAULT_REPO
        issue_number = req.issue_number
        session_id = f"issue-{issue_number}-{uuid.uuid4().hex}" if issue_number else str(uuid.uuid4())

        worktree_path = None
        branch_name = None
        if issue_number:
            worktree_path, branch_name = self._setup_worktree(repo, issue_number)

        title = req.title or (f"Issue #{issue_number}" if issue_number else "Ad-hoc Agent Task")
        session = AgentSessionInfo(
            session_id=session_id,
            repo=repo,
            issue_number=issue_number,
            title=title,
            status=AgentStatus.INITIALIZING,
            worktree_path=worktree_path,
            git_branch=branch_name or req.worktree_branch or "main",
        )
        self.sessions[session_id] = session
        self._context_queues[session_id] = asyncio.Queue()

        # Add initial user prompt message
        initial_msg = ConversationMessage(
            id=str(uuid.uuid4()),
            role=MessageRole.USER,
            content=req.prompt
        )
        session.messages.append(initial_msg)
        await self.broadcast("session_created", session.model_dump())

        # Start execution in background task
        task = asyncio.create_task(self._run_agent_loop(session_id, req.prompt, worktree_path))
        self._tasks[session_id] = task
        return session

    async def restart_agent(self, session_id: str) -> Optional[AgentSessionInfo]:
        session = self.sessions.get(session_id)
        if not session:
            return None

        # Stop existing process or task
        await self.stop_agent(session_id, reason="Restarted by user")

        session.status = AgentStatus.INITIALIZING
        session.error_message = None
        restart_msg = ConversationMessage(
            id=str(uuid.uuid4()),
            role=MessageRole.SYSTEM,
            content="Agent session was refreshed and restarted."
        )
        session.messages.append(restart_msg)
        await self.broadcast("session_updated", session.model_dump())

        # Reset queue
        self._context_queues[session_id] = asyncio.Queue()

        # Re-launch agent loop with the original prompt
        initial_prompt = session.messages[0].content if session.messages else f"Execute task for issue #{session.issue_number}"
        task = asyncio.create_task(self._run_agent_loop(session_id, initial_prompt, session.worktree_path))
        self._tasks[session_id] = task
        logger.info(f"Agent {session_id} restarted successfully.")
        return session

    async def stop_agent(self, session_id: str, reason: str = "Stopped by user") -> bool:
        session = self.sessions.get(session_id)
        if not session:
            return False

        proc = self._active_agents.get(session_id)
        if proc and hasattr(proc, 'terminate'):
            try:
                proc.terminate()
            except Exception:
                pass

        task = self._tasks.get(session_id)
        if task and not task.done():
            task.cancel()

        session.status = AgentStatus.STOPPED
        stop_msg = ConversationMessage(
            id=str(uuid.uuid4()),
            role=MessageRole.SYSTEM,
            content=f"Agent stopped. Reason: {reason}"
        )
        session.messages.append(stop_msg)
        await self.broadcast("session_updated", session.model_dump())
        logger.info(f"Agent {session_id} stopped: {reason}")
        return True

    async def add_context(self, session_id: str, context: str) -> bool:
        """Injects user response / instructions into the agent and ensures immediate execution."""
        session = self.sessions.get(session_id)
        if not session:
            return False

        # Add message to history
        user_msg = ConversationMessage(
            id=str(uuid.uuid4()),
            role=MessageRole.USER,
            content=context
        )
        session.messages.append(user_msg)
        await self.broadcast("message_added", {"session_id": session_id, "message": user_msg.model_dump()})

        # Put context into the active agent queue
        queue = self._context_queues.get(session_id)
        if queue:
            await queue.put(context)

        # Check if background task is actively running
        task = self._tasks.get(session_id)
        if not task or task.done():
            logger.info(f"Session {session_id} was idle/done; waking up agent with continuation turn for new user message.")
            session.status = AgentStatus.RUNNING
            session.error_message = None
            await self.broadcast("session_updated", session.model_dump())
            new_task = asyncio.create_task(
                self._run_agent_loop(session_id, context, session.worktree_path, is_continuation=True)
            )
            self._tasks[session_id] = new_task
        else:
            session.status = AgentStatus.RUNNING
            await self.broadcast("session_updated", session.model_dump())

        return True

    async def _append_message(self, session_id: str, role: MessageRole, content: str, tool_name: Optional[str] = None, tool_args: Optional[dict] = None) -> ConversationMessage:
        session = self.sessions[session_id]
        msg = ConversationMessage(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            tool_name=tool_name,
            tool_args=tool_args
        )
        session.messages.append(msg)
        if role == MessageRole.TOOL_CALL:
            session.turn_count += 1
        await self.broadcast("message_added", {"session_id": session_id, "message": msg.model_dump()})
        return msg

    async def _broadcast_token(self, session_id: str, token: str):
        session = self.sessions[session_id]
        session.token_count += 1
        await self.broadcast("token_stream", {"session_id": session_id, "token": token})

    async def _run_agent_loop(self, session_id: str, initial_prompt: str, worktree_path: Optional[str], is_continuation: bool = False):
        session = self.sessions[session_id]
        try:
            session.status = AgentStatus.RUNNING
            from agent_manager.config import AGY_CLI_PATH, AGY_MODE, MAX_SESSION_TOKENS
            cwd_dir = worktree_path or str(WORKSPACE_BASE)
            issue_num = session.issue_number or 0
            branch_name = session.git_branch or f"feat/issue-{issue_num}"

            session.agy_mode = AGY_MODE
            logger.info(f"Launching Antigravity CLI (agy) for session {session_id} on Issue #{issue_num} in mode '{AGY_MODE}'")

            agy_prompt = (
                f"You are the autonomous agent working on Issue #{issue_num} in {session.repo}. "
                f"Read AGENTS.md rules. Work inside isolated worktree {cwd_dir} on branch {branch_name}. "
                f"Implement the requested feature, verify tests, and open a PR."
            )

            # Option 1: Desktop Terminal Window (Default)
            if AGY_MODE == "terminal":
                escaped_prompt = agy_prompt.replace('"', '\"')
                session.terminal_command = f'& "{AGY_CLI_PATH}" --dangerously-skip-permissions -i "{escaped_prompt}"'
                
                # Write a one-click launcher batch file into the worktree
                try:
                    launcher_bat = Path(cwd_dir) / "launch-agy-terminal.bat"
                    launcher_bat.write_text(f'@echo off\nchcp 65001 > nul\ntitle Antigravity CLI - Issue #{issue_num}\n"{AGY_CLI_PATH}" --dangerously-skip-permissions -i "{escaped_prompt}"\npause\n', encoding="utf-8")
                except Exception as bat_err:
                    logger.debug(f"Could not write launcher bat: {bat_err}")

                await self._append_message(
                    session_id,
                    MessageRole.SYSTEM,
                    f"🖥️ [Option 1: Desktop Terminal] Launched Antigravity CLI (agy) for Issue #{issue_num}.\n"
                    f"Command: {session.terminal_command}\n"
                    f"Launcher script created: {cwd_dir}\\launch-agy-terminal.bat"
                )

                # Launch visible interactive PowerShell window
                ps_cmd = (
                    f'powershell -NoExit -Command '
                    f'"$host.ui.RawUI.WindowTitle = \'Antigravity CLI (agy) - Issue #{issue_num}\'; '
                    f'& \'{AGY_CLI_PATH}\' --dangerously-skip-permissions -i \'{agy_prompt}\'"'
                )

                proc = subprocess.Popen(
                    f'start {ps_cmd}',
                    cwd=str(cwd_dir),
                    shell=True
                )
                self._active_agents[session_id] = proc

                await self._append_message(
                    session_id,
                    MessageRole.TOOL_RESULT,
                    f"[Option 1 Active] AGY Interactive Terminal TUI\n"
                    f"Status: ACTIVELY RUNNING\n"
                    f"Tip: If running headlessly or window did not appear due to Windows session isolation, "
                    f"run launch-agy-terminal.bat in {cwd_dir} or switch to Web Stream (Option 2) in Settings.",
                    tool_name="agy_terminal_launcher"
                )

                # Keep session active and monitor context queue
                queue = self._context_queues[session_id]
                while session.status not in [AgentStatus.STOPPED, AgentStatus.FAILED, AgentStatus.COMPLETED]:
                    try:
                        next_ctx = await asyncio.wait_for(queue.get(), timeout=5.0)
                        await self._append_message(session_id, MessageRole.USER, next_ctx)
                    except asyncio.TimeoutError:
                        pass
                return

            # Option 2: Live Stream into Web Dashboard (Override)
            else:
                await self._append_message(
                    session_id,
                    MessageRole.SYSTEM,
                    f"🌐 [Option 2: Web Stream Override] Running Antigravity CLI headlessly and streaming thoughts and tool calls live into this dashboard..."
                )
                await self.broadcast("session_updated", session.model_dump())

                cmd_args = [
                    str(AGY_CLI_PATH),
                    "--dangerously-skip-permissions",
                    "--output-format", "stream-json"
                ]
                if is_continuation:
                    cmd_args.extend(["--continue", "-p", initial_prompt])
                else:
                    cmd_args.extend(["-p", agy_prompt])

                proc = await asyncio.create_subprocess_exec(
                    *cmd_args,
                    cwd=str(cwd_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                self._active_agents[session_id] = proc

                import json
                while True:
                    line_bytes = await proc.stdout.readline()
                    if not line_bytes:
                        break
                    line_str = line_bytes.decode('utf-8', errors='replace').strip()
                    if not line_str:
                        continue
                    try:
                        event_obj = json.loads(line_str)
                        ev = event_obj.get("event")
                        if ev == "step_update":
                            step = event_obj.get("step_update", {})
                            stype = step.get("step_type")
                            sstate = step.get("state")

                            # Capture live token usage metrics
                            usage = step.get("usage")
                            if usage:
                                session.input_tokens = usage.get("input_tokens", session.input_tokens)
                                session.output_tokens = usage.get("output_tokens", session.output_tokens)
                                session.thinking_tokens = usage.get("thinking_tokens", session.thinking_tokens)
                                session.cache_read_tokens = usage.get("cache_read_tokens", session.cache_read_tokens)
                                session.total_tokens = usage.get("total_tokens", session.total_tokens)
                                session.token_count = session.total_tokens
                                session.quota_percent = min(100.0, round((session.total_tokens / MAX_SESSION_TOKENS) * 100, 1))

                                # TOKEN LIMIT GUARDRAIL
                                if session.total_tokens >= MAX_SESSION_TOKENS:
                                    session.status = AgentStatus.PAUSED
                                    session.error_message = f"Token budget limit reached ({session.total_tokens:,} / {MAX_SESSION_TOKENS:,} tokens)."
                                    await self._append_message(
                                        session_id,
                                        MessageRole.SYSTEM,
                                        f"⚠️ [Token Budget Guardrail] Reached 100% of session quota ({session.total_tokens:,} tokens). "
                                        f"Agent execution safely paused without losing work. All changes in {cwd_dir} preserved. "
                                        f"You can click 'Resume' or raise your limit in Settings."
                                    )
                                    if proc.returncode is None:
                                        proc.terminate()
                                    await self.broadcast("session_updated", session.model_dump())
                                    return

                                await self.broadcast("session_updated", session.model_dump())

                            if "duration_seconds" in step:
                                session.duration_seconds = step.get("duration_seconds", session.duration_seconds)

                            if stype == "tool":
                                tname = step.get("tool_name", "tool")
                                tinfo = step.get("tool_info", {})
                                if sstate == "ACTIVE":
                                    await self._append_message(
                                        session_id,
                                        MessageRole.TOOL_CALL,
                                        f"Tool Call: {tname}",
                                        tool_name=tname,
                                        tool_args=tinfo.get("parameters")
                                    )
                                elif sstate == "DONE":
                                    await self._append_message(
                                        session_id,
                                        MessageRole.TOOL_RESULT,
                                        str(tinfo.get("output", "Done")),
                                        tool_name=tname
                                    )
                            elif stype == "agent_response":
                                delta = step.get("text_delta")
                                if delta:
                                    await self._broadcast_token(session_id, delta)
                                if sstate == "DONE" and delta:
                                    await self._append_message(session_id, MessageRole.AGENT, delta)
                        elif ev == "result":
                            res_info = event_obj.get("result", {})
                            final_resp = res_info.get("response", "Agent finished task.")

                            # Capture final result usage metrics
                            final_usage = res_info.get("usage")
                            if final_usage:
                                session.input_tokens = final_usage.get("input_tokens", session.input_tokens)
                                session.output_tokens = final_usage.get("output_tokens", session.output_tokens)
                                session.thinking_tokens = final_usage.get("thinking_tokens", session.thinking_tokens)
                                session.cache_read_tokens = final_usage.get("cache_read_tokens", session.cache_read_tokens)
                                session.total_tokens = final_usage.get("total_tokens", session.total_tokens)
                                session.token_count = session.total_tokens

                            if "duration_seconds" in res_info:
                                session.duration_seconds = res_info.get("duration_seconds", session.duration_seconds)

                            await self._append_message(session_id, MessageRole.AGENT, final_resp)
                            session.status = AgentStatus.COMPLETED
                            await self.broadcast("session_updated", session.model_dump())
                    except Exception as json_err:
                        logger.debug(f"JSON stream line parse info: {json_err}")

                await proc.wait()
                if session.status != AgentStatus.COMPLETED:
                    session.status = AgentStatus.COMPLETED if proc.returncode == 0 else AgentStatus.FAILED
                await self.broadcast("session_updated", session.model_dump())
                return
        except asyncio.CancelledError:
            session.status = AgentStatus.STOPPED
            logger.info(f"Agent session {session_id} task was cancelled.")
        except Exception as e:
            session.status = AgentStatus.FAILED
            session.error_message = str(e)
            logger.exception(f"Error during agent session {session_id}: {e}")
            await self._append_message(session_id, MessageRole.SYSTEM, f"Agent encountered error: {str(e)}")
        finally:
            self._active_agents.pop(session_id, None)
            await self.broadcast("session_updated", session.model_dump())
