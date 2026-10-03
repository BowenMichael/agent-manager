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
            if session.status in [AgentStatus.PAUSED, AgentStatus.COMPLETED]:
                session.status = AgentStatus.RUNNING
                await self.broadcast("session_updated", session.model_dump())
            return True
        return False

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

    async def _run_agent_loop(self, session_id: str, initial_prompt: str, worktree_path: Optional[str]):
        session = self.sessions[session_id]
        try:
            session.status = AgentStatus.RUNNING
            await self.broadcast("session_updated", session.model_dump())

            # Launch visible interactive terminal worker that starts working immediately!
            cwd_dir = worktree_path or str(WORKSPACE_BASE)
            issue_num = session.issue_number or 0
            branch_name = session.git_branch or f"feat/issue-{issue_num}"
            project_root = Path(__file__).resolve().parent.parent

            logger.info(f"Launching visible terminal worker for session {session_id} on Issue #{issue_num}")
            await self._append_message(
                session_id,
                MessageRole.SYSTEM,
                f"Launched dedicated interactive terminal for Issue #{issue_num}. Agent started working immediately."
            )

            # PowerShell command in visible window
            worker_cmd = (
                f'powershell -NoExit -Command '
                f'"$host.ui.RawUI.WindowTitle = \'AGY Terminal Agent - Issue #{issue_num}\'; '
                f'python -u -m agent_manager.worker --session-id \'{session_id}\' --issue {issue_num} '
                f'--repo \'{session.repo}\' --worktree \'{cwd_dir}\' --branch \'{branch_name}\'"'
            )

            # Use 'start' to open visible PowerShell terminal window
            proc = subprocess.Popen(
                f'start {worker_cmd}',
                cwd=str(project_root),
                shell=True
            )
            self._active_agents[session_id] = proc

            await self._append_message(
                session_id,
                MessageRole.TOOL_RESULT,
                f"[Terminal Launched] Title: AGY Terminal Agent - Issue #{issue_num}\nStatus: ACTIVELY WORKING IN TERMINAL",
                tool_name="terminal_launcher"
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
