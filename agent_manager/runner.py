import agent_manager.config as config
import os
import uuid
import json
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import WebSocket

from agent_manager.config import (
    DEFAULT_REPO, WORKSPACE_BASE, AGY_CLI_PATH,
    AGY_MODE, MAX_SESSION_TOKENS, COMPACT_COMPLETED_CHAT,
    IS_SERVER, CLI_IDLE_TIMEOUT_MINUTES
)
from agent_manager.models import (
    AgentSessionInfo, AgentStatus, ConversationMessage,
    MessageRole, SpawnRequest, WorkflowStage
)
from agent_manager.storage import save_sessions, load_sessions
from agent_manager.github import post_issue_comment
from agent_manager.utils.command_formatter import format_command_output
from agent_manager.utils.workspace import find_local_workspace
from agent_manager.formatters.comments import (
    format_agent_comment,
    format_agent_metadata_footer,
    BADGE_AGENT_PAUSED,
    BADGE_AGENT_UPDATE,
    FOOTER_SIGNATURE
)

logger = logging.getLogger("agent_manager.runner")

QUOTA_PATTERNS = (
    "quota", "resource_exhausted", "resource exhausted", "rate limit", "rate_limit",
    "429", "too many requests", "usage limit", "limit reached", "out of credits",
)

def _looks_like_quota_error(text: str) -> bool:
    t = (text or "").lower()
    return any(p in t for p in QUOTA_PATTERNS)

def format_tool_display(tool_name: str, tool_args: Optional[dict] = None) -> tuple[str, str]:
    """Generates a human-friendly tool call title and descriptive summary from tool arguments."""
    name = tool_name or "tool"
    args = tool_args or {}

    if name == "view_file":
        target = args.get("AbsolutePath") or args.get("path") or ""
        base = target.replace("\\", "/").rstrip("/").split("/")[-1] if target else ""
        title = f"View File: {base}" if base else "View File"
        start_line = args.get("StartLine")
        end_line = args.get("EndLine")
        line_info = f" (lines {start_line}-{end_line})" if start_line is not None and end_line is not None else ""
        action = args.get("toolAction") or args.get("toolSummary")
        action_prefix = f"[{action}] " if action else ""
        desc = f"{action_prefix}{target}{line_info}".strip() or "Viewing file"
        return title, desc

    if name in ("replace_file_content", "write_to_file", "multi_replace_file_content"):
        target = args.get("TargetFile") or args.get("path") or ""
        base = target.replace("\\", "/").rstrip("/").split("/")[-1] if target else ""
        verb = "Write File" if name == "write_to_file" else "Edit File"
        title = f"{verb}: {base}" if base else verb
        instruction = args.get("Instruction") or args.get("Description") or args.get("toolAction") or args.get("toolSummary") or ""
        instr_str = f" - {instruction}" if instruction else ""
        desc = f"{target}{instr_str}".strip() or f"{verb} operation"
        return title, desc

    if name == "run_command":
        cmd = args.get("CommandLine") or args.get("command") or ""
        summary = args.get("toolSummary") or args.get("toolAction")
        title = f"Run: {summary}" if summary else "Run Command"
        desc = cmd or "Running shell command"
        return title, desc

    if name == "call_mcp_tool":
        sub_tool = args.get("ToolName") or "mcp_tool"
        server = args.get("ServerName")
        server_str = f"[{server}] " if server else ""
        title = f"MCP: {server_str}{sub_tool}"
        sub_args = args.get("Arguments")
        sub_args_str = json.dumps(sub_args) if isinstance(sub_args, dict) else (str(sub_args) if sub_args else "")
        desc = f"{sub_tool}({sub_args_str})" if sub_args_str else sub_tool
        return title, desc

    # Generic tool fallback
    summary = args.get("toolSummary") or args.get("toolAction")
    title = f"{name}: {summary}" if summary else f"Tool Call: {name}"
    # Summarize key parameters
    params_summary = []
    for k, v in list(args.items())[:3]:
        if k in ("toolAction", "toolSummary"):
            continue
        v_str = str(v)
        if len(v_str) > 60:
            v_str = v_str[:57] + "..."
        params_summary.append(f"{k}={v_str}")
    desc = ", ".join(params_summary) if params_summary else f"Executing {name}"
    return title, desc

def get_repository_context(cwd_dir: str) -> str:
    """
    Gathers key repository architecture context (directory structure, manifest files,
    configs, and recent git history) to inject into the Stage 2 planning prompt.
    """
    import subprocess
    from pathlib import Path

    context_lines = []
    root = Path(cwd_dir)
    if not root.exists():
        return "Repository directory not found."

    # 1. Top-level files and directories (excluding noise)
    excluded = {".git", ".worktrees", "node_modules", ".next", "dist", "build", "__pycache__", ".venv", "venv", ".idea", ".vscode"}
    try:
        entries = sorted([p.name + ("/" if p.is_dir() else "") for p in root.iterdir() if p.name not in excluded and not p.name.startswith(".")])
        if entries:
            context_lines.append(f"**Directory Structure (Top Level)**:\n`{'`, `'.join(entries)}`")
    except Exception as e:
        context_lines.append(f"Directory listing error: {e}")

    # 2. Key configuration and manifest inspection
    configs_to_check = [
        "package.json", "vercel.json", "next.config.js", "next.config.mjs",
        "tsconfig.json", "requirements.txt", "pyproject.toml", "Dockerfile", "render.yaml"
    ]
    for cfg in configs_to_check:
        cfg_path = root / cfg
        if cfg_path.exists() and cfg_path.is_file():
            try:
                content = cfg_path.read_text(encoding="utf-8", errors="replace").strip()
                if len(content) > 1500:
                    content = content[:1500] + "\n... (truncated)"
                context_lines.append(f"**Configuration File (`{cfg}`)**:\n```\n{content}\n```")
            except Exception:
                pass

    # 3. Recent git commits for context
    try:
        res = subprocess.run(
            ["git", "log", "-n", "3", "--oneline"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5
        )
        if res.returncode == 0 and res.stdout.strip():
            context_lines.append(f"**Recent Git History**:\n```\n{res.stdout.strip()}\n```")
    except Exception:
        pass

    return "\n\n".join(context_lines) if context_lines else "No additional repository context discovered."

class AgentRunnerManager:
    _instance: Optional["AgentRunnerManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_manager()
        return cls._instance

    def _init_manager(self):
        self._watchdog_task = None

        # Load cached sessions from persistent disk storage
        self.sessions: Dict[str, AgentSessionInfo] = load_sessions()
        self._active_agents: Dict[str, asyncio.subprocess.Process] = {}
        self._context_queues: Dict[str, asyncio.Queue] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._ws_connections: List[WebSocket] = []

        # Re-initialize context queues for all cached sessions
        for sid in self.sessions:
            self._context_queues[sid] = asyncio.Queue()

    def _save(self):
        """Persists current sessions state to disk."""
        try:
            save_sessions(self.sessions)
        except Exception as e:
            logger.error(f"Error persisting sessions: {e}")

    def register_ws(self, websocket: WebSocket):
        if websocket not in self._ws_connections:
            self._ws_connections.append(websocket)

    def unregister_ws(self, websocket: WebSocket):
        if websocket in self._ws_connections:
            self._ws_connections.remove(websocket)

    async def broadcast(self, event_type: str, data: dict):
        if not self._ws_connections:
            return
        payload = json.dumps({"type": event_type, "data": data})
        stale = []
        for ws in self._ws_connections:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)
        for dead in stale:
            self.unregister_ws(dead)

    def list_sessions(self, include_archived: bool = True) -> List[AgentSessionInfo]:
        if include_archived:
            return list(self.sessions.values())
        return [s for s in self.sessions.values() if not s.is_archived]

    def get_session(self, session_id: str) -> Optional[AgentSessionInfo]:
        return self.sessions.get(session_id)

    def _setup_worktree(self, repo: str, issue_number: int) -> tuple[Optional[str], Optional[str]]:
        """Sets up isolated git worktree for the issue to prevent branch conflicts."""
        repo_dir = find_local_workspace(repo)

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

        pipeline_enabled = req.workflow_pipeline_enabled if req.workflow_pipeline_enabled is not None else getattr(config, "WORKFLOW_PIPELINE_ENABLED", False)
        title = req.title or (f"Issue #{issue_number}" if issue_number else "Ad-hoc Agent Task")
        session = AgentSessionInfo(
            session_id=session_id,
            repo=repo,
            issue_number=issue_number,
            title=title,
            status=AgentStatus.INITIALIZING,
            worktree_path=worktree_path,
            git_branch=branch_name or req.worktree_branch or "main",
            model=req.model or getattr(config, "DEFAULT_MODEL", "gemini-3.8-flash"),
            effort=req.effort or getattr(config, "DEFAULT_EFFORT", "high"),
            workflow_pipeline_enabled=pipeline_enabled,
            workflow_stage=WorkflowStage.SUMMARIZING if pipeline_enabled else WorkflowStage.DIRECT
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
        self._save()
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
        session.turn_count = 0
        session.consecutive_duplicate_tool_count = 0
        session.consecutive_view_file_count = 0
        session.last_tool_signature = None
        session.circuit_breaker_triggered = False
        # Apply updated model and effort settings on restart
        session.model = getattr(config, "DEFAULT_MODEL", session.model or "gemini-3.8-flash")
        session.effort = getattr(config, "DEFAULT_EFFORT", session.effort or "high")

        restart_msg = ConversationMessage(
            id=str(uuid.uuid4()),
            role=MessageRole.SYSTEM,
            content=f"🔄 Agent session restarted with model: {session.model} (effort: {session.effort})."
        )
        session.messages.append(restart_msg)
        self._save()
        await self.broadcast("session_updated", session.model_dump())

        # Reset queue
        self._context_queues[session_id] = asyncio.Queue()

        # Re-launch agent loop with the original prompt
        initial_prompt = session.messages[0].content if session.messages else f"Execute task for issue #{session.issue_number}"
        task = asyncio.create_task(self._run_agent_loop(session_id, initial_prompt, session.worktree_path))
        self._tasks[session_id] = task
        logger.info(f"Agent {session_id} restarted successfully.")
        return session

    async def resume_agent(self, session_id: str) -> bool:
        """Resumes a paused agent session (e.g. after raising token limit or resetting circuit breaker)."""
        session = self.sessions.get(session_id)
        if not session:
            return False

        session.status = AgentStatus.RUNNING
        session.error_message = None
        session.quota_exceeded = False
        session.quota_message = None
        session.turn_count = 0
        session.consecutive_duplicate_tool_count = 0
        session.consecutive_view_file_count = 0
        session.last_tool_signature = None
        session.circuit_breaker_triggered = False
        # Apply updated model and effort settings on resume
        session.model = getattr(config, "DEFAULT_MODEL", session.model or "gemini-3.8-flash")
        session.effort = getattr(config, "DEFAULT_EFFORT", session.effort or "high")

        resume_msg = ConversationMessage(
            id=str(uuid.uuid4()),
            role=MessageRole.SYSTEM,
            content=f"▶️ Session resumed by user with model: {session.model} (effort: {session.effort}). Continuing execution in isolated worktree."
        )
        session.messages.append(resume_msg)
        self._save()
        await self.broadcast("session_updated", session.model_dump())

        # Re-trigger continuation
        task = asyncio.create_task(
            self._run_agent_loop(session_id, "Continue working on the task and conclude your remaining deliverables.", session.worktree_path, is_continuation=True)
        )
        self._tasks[session_id] = task
        return True

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
            content=f"⏹️ Agent stopped. Reason: {reason}"
        )
        session.messages.append(stop_msg)
        self._save()
        await self.broadcast("session_updated", session.model_dump())
        logger.info(f"Agent {session_id} stopped: {reason}")
        return True

    async def compact_session(self, session_id: str, force: bool = False) -> bool:
        """
        Compacts / compresses the chat transcript to optimize tokens and eliminate noise.
        Compresses verbose tool execution logs, intermediate results, and thoughts
        into a clean structured summary while preserving critical user instructions and deliverables.
        """
        session = self.sessions.get(session_id)
        if not session or not session.messages:
            return False

        if session.is_compacted and not force:
            return False

        should_compact = force or getattr(config, "COMPACT_COMPLETED_CHAT", COMPACT_COMPLETED_CHAT)
        if not should_compact:
            return False

        original_msgs = session.messages
        user_msgs = [m for m in original_msgs if m.role == MessageRole.USER]
        agent_msgs = [m for m in original_msgs if m.role == MessageRole.AGENT]
        tool_call_count = len([m for m in original_msgs if m.role == MessageRole.TOOL_CALL])
        tool_result_count = len([m for m in original_msgs if m.role == MessageRole.TOOL_RESULT])
        thought_count = len([m for m in original_msgs if m.role == MessageRole.THOUGHT])

        # If there are only 1 or 2 messages, no compaction needed
        if len(original_msgs) <= 3 and tool_call_count == 0:
            session.is_compacted = True
            self._save()
            return True

        # Extract tools used
        tools_used = set()
        for m in original_msgs:
            if m.tool_name:
                tools_used.add(m.tool_name)
            elif m.role == MessageRole.TOOL_CALL and m.tool_name:
                tools_used.add(m.tool_name)

        # Preserve the initial prompt / user instructions
        initial_prompt = user_msgs[0].content if user_msgs else (session.title or "Initial task")
        
        # Collect final deliverable / response
        latest_agent_resp = agent_msgs[-1].content if agent_msgs else "Task completed successfully."
        
        compacted_summary_lines = [
            f"📦 **Chat Compacted & Compressed (Token Optimization)**",
            f"- **Execution Summary**: Completed {tool_call_count} tool actions ({', '.join(sorted(tools_used)) if tools_used else 'direct execution'}).",
            f"- **Compressed Artifacts**: Compacted {tool_call_count + tool_result_count} tool messages and {thought_count} thought traces.",
            f"- **Tokens Recorded**: {session.total_tokens:,} tokens ({session.input_tokens:,} input / {session.output_tokens:,} output / {session.thinking_tokens:,} reasoning)."
        ]
        summary_text = "\n".join(compacted_summary_lines)

        new_messages: List[ConversationMessage] = []

        # 1. Keep initial user instruction
        if user_msgs:
            new_messages.append(user_msgs[0])

        # 2. Add the compacted summary badge / note
        new_messages.append(ConversationMessage(
            id=str(uuid.uuid4()),
            role=MessageRole.SYSTEM,
            content=summary_text
        ))

        # 3. If there were subsequent user prompts (multi-turn), retain them
        if len(user_msgs) > 1:
            for extra_user_msg in user_msgs[1:]:
                new_messages.append(extra_user_msg)

        # 4. Retain the final agent response / deliverable
        if agent_msgs:
            new_messages.append(agent_msgs[-1])

        session.messages = new_messages
        session.is_compacted = True
        session.compact_summary = summary_text
        self._save()
        await self.broadcast("session_updated", session.model_dump())
        logger.info(f"Agent session {session_id} chat transcript compacted successfully ({len(original_msgs)} -> {len(new_messages)} messages).")
        return True

    async def complete_agent(self, session_id: str, reason: str = "Issue moved to 'Done' on Project Board") -> bool:
        """Formally completes and archives the session when the issue card enters 'Done'."""
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

        session.status = AgentStatus.COMPLETED
        complete_msg = ConversationMessage(
            id=str(uuid.uuid4()),
            role=MessageRole.SYSTEM,
            content=f"✅ [Task Completed & Archived] {reason}. Chat session has concluded successfully."
        )
        session.messages.append(complete_msg)

        # Automatically compress / compact chat when process is completed
        await self.compact_session(session_id)

        self._save()
        await self.broadcast("session_updated", session.model_dump())
        logger.info(f"Agent {session_id} completed: {reason}")
        return True

    async def archive_agent(self, session_id: str) -> bool:
        """Archives an agent session to remove it from the primary active list."""
        session = self.sessions.get(session_id)
        if not session:
            return False

        # Stop active subprocess if running
        proc = self._active_agents.get(session_id)
        if proc and hasattr(proc, 'terminate'):
            try:
                proc.terminate()
            except Exception:
                pass
            self._active_agents.pop(session_id, None)

        task = self._tasks.get(session_id)
        if task and not task.done():
            task.cancel()

        session.is_archived = True
        from datetime import datetime
        session.archived_at = datetime.utcnow().isoformat()
        if session.status in [AgentStatus.RUNNING, AgentStatus.INITIALIZING]:
            session.status = AgentStatus.STOPPED

        archive_msg = ConversationMessage(
            id=str(uuid.uuid4()),
            role=MessageRole.SYSTEM,
            content="📦 [Agent Archived] This agent session has been archived."
        )
        session.messages.append(archive_msg)
        self._save()
        await self.broadcast("session_updated", session.model_dump())
        logger.info(f"Agent {session_id} archived.")
        return True

    async def unarchive_agent(self, session_id: str) -> bool:
        """Restores an archived agent session back to the active list."""
        session = self.sessions.get(session_id)
        if not session:
            return False

        session.is_archived = False
        session.archived_at = None
        unarchive_msg = ConversationMessage(
            id=str(uuid.uuid4()),
            role=MessageRole.SYSTEM,
            content="📂 [Agent Restored] This agent session has been restored from archive."
        )
        session.messages.append(unarchive_msg)
        self._save()
        await self.broadcast("session_updated", session.model_dump())
        logger.info(f"Agent {session_id} unarchived.")
        return True

    async def delete_agent(self, session_id: str) -> bool:
        """Permanently removes an agent session."""
        session = self.sessions.get(session_id)
        if not session:
            return False

        proc = self._active_agents.get(session_id)
        if proc and hasattr(proc, 'terminate'):
            try:
                proc.terminate()
            except Exception:
                pass
            self._active_agents.pop(session_id, None)

        task = self._tasks.get(session_id)
        if task and not task.done():
            task.cancel()

        self.sessions.pop(session_id, None)
        self._context_queues.pop(session_id, None)
        self._save()
        await self.broadcast("session_deleted", {"session_id": session_id})
        logger.info(f"Agent {session_id} deleted permanently.")
        return True

    async def add_context(self, session_id: str, context: str) -> bool:
        """Injects user response / instructions into the agent. Applies latest model & effort settings for the prompt."""
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
        session.is_stalled = False
        session.quota_exceeded = False
        session.quota_message = None
        session.turn_count = 0
        session.consecutive_duplicate_tool_count = 0
        session.consecutive_view_file_count = 0
        session.last_tool_signature = None
        session.circuit_breaker_triggered = False
        session.current_activity = "Processing new user instructions..."

        # Apply updated model and effort for this prompt
        current_cfg_model = getattr(config, "DEFAULT_MODEL", "gemini-3.8-flash")
        current_cfg_effort = getattr(config, "DEFAULT_EFFORT", "high")
        if session.model != current_cfg_model or session.effort != current_cfg_effort:
            logger.info(f"Updated session {session_id} to model={current_cfg_model}, effort={current_cfg_effort} for next prompt.")
            session.model = current_cfg_model
            session.effort = current_cfg_effort

        self._save()
        await self.broadcast("message_added", {"session_id": session_id, "message": user_msg.model_dump()})

        # Put context into queue
        queue = self._context_queues.get(session_id)
        if queue:
            await queue.put(context)

        current_mode = getattr(config, "AGY_MODE", AGY_MODE)
        proc = self._active_agents.get(session_id)
        if current_mode == "terminal" and proc is not None:
            # Active terminal is kept open across prompt turns to leverage server-side caching
            logger.info(f"Preserving existing interactive terminal for session {session_id} across prompt turns.")
        elif proc and hasattr(proc, 'terminate'):
            logger.info(f"Interrupting active/stalled process for session {session_id} to process new user context.")
            try:
                proc.terminate()
            except Exception:
                pass
            self._active_agents.pop(session_id, None)

        task = self._tasks.get(session_id)
        if task and not task.done():
            task.cancel()

        logger.info(f"Starting continuation turn for session {session_id} with newly injected context.")
        session.status = AgentStatus.RUNNING
        session.error_message = None
        self._save()
        await self.broadcast("session_updated", session.model_dump())

        new_task = asyncio.create_task(
            self._run_agent_loop(session_id, context, session.worktree_path, is_continuation=True)
        )
        self._tasks[session_id] = new_task
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
        self._save()
        await self.broadcast("message_added", {"session_id": session_id, "message": msg.model_dump()})
        return msg

    async def _run_cli_turn(self, session_id: str, prompt: str, cwd_dir: str, model: str, effort: str) -> str:
        """Runs a single prompt turn via Antigravity CLI and returns the generated text response."""
        from agent_manager.config import AGY_CLI_PATH, resolve_model_and_effort
        session = self.sessions[session_id]
        clean_model, clean_effort, cli_model_args = resolve_model_and_effort(model, effort)
        cmd_args = [
            str(AGY_CLI_PATH),
            *cli_model_args,
            "--dangerously-skip-permissions",
            "--output-format", "stream-json",
            "-p", prompt
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            cwd=str(cwd_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        self._active_agents[session_id] = proc
        accumulated_text = []
        accumulated_thought = []

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

                    # Live Token Usage
                    usage = step.get("usage")
                    if usage:
                        session.input_tokens = usage.get("input_tokens", session.input_tokens)
                        session.output_tokens = usage.get("output_tokens", session.output_tokens)
                        session.thinking_tokens = usage.get("thinking_tokens", session.thinking_tokens)
                        session.total_tokens = usage.get("total_tokens", session.total_tokens)
                        session.token_count = session.total_tokens
                        self._save()
                        await self.broadcast("session_updated", session.model_dump())

                    if stype == "thought":
                        delta = step.get("text_delta")
                        if delta:
                            accumulated_thought.append(delta)
                            await self.broadcast("thought_delta", {
                                "session_id": session_id,
                                "delta": delta,
                                "model": clean_model
                            })
                            from datetime import datetime
                            session.last_activity_at = datetime.utcnow().isoformat()
                            session.is_stalled = False
                            if len(accumulated_thought) % 12 == 1:
                                recent_thought = "".join(accumulated_thought).strip()[-80:].replace("\n", " ")
                                session.current_activity = f"Planning ({clean_model}): {recent_thought}..."
                                await self.broadcast("session_updated", session.model_dump())

                    elif stype == "agent_response":
                        delta = step.get("text_delta")
                        if delta:
                            accumulated_text.append(delta)
                            await self._broadcast_token(session_id, delta)

                elif ev == "result":
                    res_info = event_obj.get("result", {})
                    final_txt = res_info.get("response")
                    if final_txt:
                        accumulated_text = [final_txt]
                    final_usage = res_info.get("usage")
                    if final_usage:
                        session.input_tokens = final_usage.get("input_tokens", session.input_tokens)
                        session.output_tokens = final_usage.get("output_tokens", session.output_tokens)
                        session.thinking_tokens = final_usage.get("thinking_tokens", session.thinking_tokens)
                        session.total_tokens = final_usage.get("total_tokens", session.total_tokens)
                        session.token_count = session.total_tokens
            except Exception:
                pass

        await proc.wait()
        self._active_agents.pop(session_id, None)

        try:
            from agent_manager.telemetry import record_token_usage
            record_token_usage(
                session_id=session_id,
                repo=session.repo or "",
                model=clean_model,
                input_tokens=session.input_tokens,
                output_tokens=session.output_tokens,
                thinking_tokens=session.thinking_tokens,
                cache_read_tokens=session.cache_read_tokens,
                total_tokens=session.total_tokens
            )
        except Exception as tel_err:
            logger.debug(f"Telemetry record error in cli turn: {tel_err}")

        if accumulated_thought:
            full_thought = "".join(accumulated_thought).strip()
            if full_thought:
                await self._append_message(session_id, MessageRole.THOUGHT, full_thought)

        return "".join(accumulated_text).strip()

    async def _run_workflow_pipeline(self, session_id: str, task_description: str, cwd_dir: str, issue_num: int, branch_name: str):
        """
        Executes Issue #36 multi-stage workflow pipeline:
        Stage 1: Dumb model summarizes issue requirements.
        Stage 2: Smart model creates an architectural plan.
        Stage 3: Dumb model executes implementation and verification.
        """
        session = self.sessions[session_id]
        from agent_manager.config import (
            PIPELINE_SUMMARY_MODEL, PIPELINE_SUMMARY_EFFORT,
            PIPELINE_PLANNING_MODEL, PIPELINE_PLANNING_EFFORT,
            PIPELINE_IMPLEMENTATION_MODEL, PIPELINE_IMPLEMENTATION_EFFORT
        )

        sum_model = getattr(config, "PIPELINE_SUMMARY_MODEL", PIPELINE_SUMMARY_MODEL)
        sum_effort = getattr(config, "PIPELINE_SUMMARY_EFFORT", PIPELINE_SUMMARY_EFFORT)
        plan_model = getattr(config, "PIPELINE_PLANNING_MODEL", PIPELINE_PLANNING_MODEL)
        plan_effort = getattr(config, "PIPELINE_PLANNING_EFFORT", PIPELINE_PLANNING_EFFORT)
        impl_model = getattr(config, "PIPELINE_IMPLEMENTATION_MODEL", PIPELINE_IMPLEMENTATION_MODEL)
        impl_effort = getattr(config, "PIPELINE_IMPLEMENTATION_EFFORT", PIPELINE_IMPLEMENTATION_EFFORT)

        # STAGE 1: ISSUE SUMMARY (Dumb Model)
        session.workflow_stage = WorkflowStage.SUMMARIZING
        session.model = sum_model
        session.effort = sum_effort
        session.current_activity = f"Stage 1/3: Summarizing requirements ({sum_model} / {sum_effort})..."
        await self._append_message(
            session_id,
            MessageRole.SYSTEM,
            f"🔄 **Pipeline Stage 1/3: Issue Summarization**\n"
            f"Using model: `{sum_model}` (effort: `{sum_effort}`)\n"
            f"Extracting core objectives, acceptance criteria, and constraints from Issue #{issue_num}..."
        )
        self._save()
        await self.broadcast("session_updated", session.model_dump())

        summary_prompt = (
            f"You are a requirements analyst. Read the following GitHub issue task description:\n\n"
            f"{task_description}\n\n"
            f"Provide a clear, structured summary:\n"
            f"1. Core Objective\n"
            f"2. Acceptance Criteria & Requirements\n"
            f"3. Key Constraints & Context\n"
            f"Keep the summary concise and focused."
        )
        summary_result = await self._run_cli_turn(session_id, summary_prompt, cwd_dir, sum_model, sum_effort)
        session.pipeline_summary = summary_result or "Summary completed."
        await self._append_message(
            session_id,
            MessageRole.AGENT,
            f"📋 **Stage 1 Summary Deliverable**:\n\n{session.pipeline_summary}"
        )
        self._save()
        await self.broadcast("session_updated", session.model_dump())

        # STAGE 2: ARCHITECTURAL PLANNING (Smart Model)
        session.workflow_stage = WorkflowStage.PLANNING
        session.model = plan_model
        session.effort = plan_effort
        session.current_activity = f"Stage 2/3: Formulating plan ({plan_model} / {plan_effort})..."

        # Gather repository architecture & codebase context
        repo_context = get_repository_context(cwd_dir)

        await self._append_message(
            session_id,
            MessageRole.SYSTEM,
            f"🧠 **Pipeline Stage 2/3: High-Reasoning Planning**\n\n"
            f"**Model**: `{plan_model}` (effort: `{plan_effort}`)\n"
            f"**Context Injected**: Directory manifest, configuration files, and git history from `{cwd_dir}`.\n\n"
            f"Formulating architectural execution plan based on Stage 1 summary and repository structure..."
        )
        self._save()
        await self.broadcast("session_updated", session.model_dump())

        planning_prompt = (
            f"You are a principal software architect. You are formulating the high-level implementation strategy for GitHub Issue #{issue_num} in {cwd_dir}.\n\n"
            f"### Issue Requirements Summary:\n{session.pipeline_summary}\n\n"
            f"### Original Task Description:\n{task_description}\n\n"
            f"### Codebase Context (Repository Structure & Configurations):\n{repo_context}\n\n"
            f"**PLANNING DIRECTIVE (Architectural Guidance over Code Implementation)**:\n"
            f"- DO NOT write full code implementations, function bodies, or large code diffs in this plan.\n"
            f"- Focus on high-level architectural design, system boundaries, and clear step-by-step instructions.\n"
            f"- Give Stage 3 (the implementation model) all the structural guidance, file targets, and verification criteria it needs so it can write the code itself.\n\n"
            f"Provide a structured plan containing:\n"
            f"1. **Architectural Overview**: Conceptual approach, component interactions, and key design decisions.\n"
            f"2. **Target Files & Modular Breakdown**: Exact files to create or modify. STRICT ANTI-MONOLITH RULE: Keep all files under 250 lines; decompose into dedicated modular files (`models/`, `services/`, `components/`, `utils/`).\n"
            f"3. **Step-by-Step Implementation Guide**: Clear, ordered instructions specifying WHAT each component must accomplish without writing full code blocks.\n"
            f"4. **Verification & Testing Criteria**: Expected behavior, test commands to run, and verification checklist (with command log suppression)."
        )
        plan_result = await self._run_cli_turn(session_id, planning_prompt, cwd_dir, plan_model, plan_effort)
        session.pipeline_plan = plan_result or "Plan formulated."
        await self._append_message(
            session_id,
            MessageRole.AGENT,
            f"📐 **Stage 2 Plan Deliverable**:\n\n{session.pipeline_plan}"
        )
        self._save()

        await self.broadcast("session_updated", session.model_dump())

        # STAGE 3: IMPLEMENTATION (Dumb Model)
        session.workflow_stage = WorkflowStage.IMPLEMENTING
        session.model = impl_model
        session.effort = impl_effort
        session.current_activity = f"Stage 3/3: Implementing code ({impl_model} / {impl_effort})..."
        await self._append_message(
            session_id,
            MessageRole.SYSTEM,
            f"⚡ **Pipeline Stage 3/3: Execution & Implementation**\n"
            f"Using implementation model: `{impl_model}` (effort: `{impl_effort}`)\n"
            f"Executing changes in isolated worktree `{cwd_dir}` according to the plan..."
        )
        self._save()
        await self.broadcast("session_updated", session.model_dump())

        implementation_prompt = (
            f"You are operating autonomously on GitHub Issue #{issue_num}.\n"
            f"Working Directory: {cwd_dir}\n"
            f"Git Branch: {branch_name}\n\n"
            f"### Approved Implementation Plan:\n{session.pipeline_plan}\n\n"
            f"### Issue Context & Summary:\n{session.pipeline_summary}\n\n"
            f"Execute the steps in the plan now. Modify the required files, run unit tests to verify, and summarize your completed work.\n"
            f"Follow AGENTS.md conventions."
        )

        # Execute final implementation via standard runner loop
        await self._run_agent_loop(session_id, implementation_prompt, cwd_dir, is_continuation=True)

    async def _broadcast_token(self, session_id: str, token: str):
        session = self.sessions[session_id]
        session.token_count += 1
        await self.broadcast("token_stream", {"session_id": session_id, "token": token})

    async def _run_agent_loop(self, session_id: str, initial_prompt: str, worktree_path: Optional[str], is_continuation: bool = False):
        session = self.sessions[session_id]
        try:
            session.status = AgentStatus.RUNNING
            self._save()
            cwd_dir = worktree_path or str(WORKSPACE_BASE)
            issue_num = session.issue_number or 0
            branch_name = session.git_branch or f"feat/issue-{issue_num}"

            from agent_manager.config import AGY_CLI_PATH, AGY_MODE, MAX_SESSION_TOKENS, resolve_model_and_effort

            # Multi-stage workflow pipeline check (Issue #36)
            if session.workflow_pipeline_enabled and not is_continuation:
                await self._run_workflow_pipeline(session_id, initial_prompt, cwd_dir, issue_num, branch_name)
                return

            # Resolve model and effort cleanly for CLI execution
            selected_model = session.model or getattr(config, "DEFAULT_MODEL", "gemini-3.8-flash")
            selected_effort = session.effort or getattr(config, "DEFAULT_EFFORT", "high")
            clean_model, clean_effort, cli_model_args = resolve_model_and_effort(selected_model, selected_effort)
            session.model = clean_model
            session.effort = clean_effort

            current_mode = getattr(config, "AGY_MODE", AGY_MODE)
            current_max_tokens = getattr(config, "MAX_SESSION_TOKENS", MAX_SESSION_TOKENS)

            # Option 1: Terminal Mode
            if current_mode == "terminal":
                existing_proc = self._active_agents.get(session_id)
                is_proc_alive = False
                if existing_proc is not None:
                    if hasattr(existing_proc, 'poll'):
                        is_proc_alive = (existing_proc.poll() is None)
                    else:
                        is_proc_alive = True

                if is_continuation and is_proc_alive:
                    from datetime import datetime
                    session.last_activity_at = datetime.utcnow().isoformat()
                    session.status = AgentStatus.IN_REVIEW
                    await self._append_message(
                        session_id,
                        MessageRole.SYSTEM,
                        f"⚡ [Option 1: Interactive Desktop Terminal] Active terminal retained for session at {cwd_dir}. "
                        f"Prompt and server-side cache preserved across prompt turns."
                    )
                    self._save()
                    await self.broadcast("session_updated", session.model_dump())
                    return

            repo_context = get_repository_context(cwd_dir)
            agy_prompt = (
                f"You are operating autonomously on GitHub Issue #{issue_num}.\n"
                f"Working Directory: {cwd_dir}\n"
                f"Git Branch: {branch_name}\n\n"
                f"Task Description:\n{initial_prompt}\n\n"
                f"Codebase Context (Repository Structure & Configurations):\n{repo_context}\n\n"
                f"RULES & EFFICIENCY GUARDRAILS:\n"
                f"1. Make changes in this directory.\n"
                f"2. Follow AGENTS.md conventions.\n"
                f"3. CRITICAL TOOL EFFICIENCY (Prevent Runaway Token Spend):\n"
                f"   - SEARCH FIRST: Always use grep_search to find exact symbol, function, or line locations BEFORE calling view_file.\n"
                f"   - SLICE READING ONLY: When calling view_file, ALWAYS supply StartLine and EndLine (max 100 lines at once). NEVER view entire large files over 200 lines.\n"
                f"   - NEVER RE-READ: Do NOT call view_file on the same file or line range twice in a row. Rely on context and proceed directly to code edits or tests.\n"
                f"4. ANTI-MONOLITH RULE: Never create monolithic files over 250 lines. Decompose logic into modular, single-responsibility files (models, services, utils, components). When modifying large files (>300 lines), extract new functions into separate helper files.\n"
                f"{('5. CIRCUIT BREAKER ACTIVE: Duplicate tool calls, excessive consecutive file reads without edits, or exceeding ' + str(getattr(config, 'MAX_TURNS_PER_SESSION', 15)) + ' turns will immediately halt execution.\n') if getattr(config, 'GUARDRAILS_ENABLED', True) else '5. SAFETY GUARDRAILS DISABLED: Unrestricted execution mode active per developer settings.\n'}"
                f"6. CRITICAL: Do NOT add, remove, or modify GitHub issue tags/labels. Board status columns are managed directly.\n"
                f"7. Once changes are ready, commit and create a pull request if appropriate.\n"
            )

            # Option 1: Terminal Mode Launch
            if current_mode == "terminal":
                title_str = f"Antigravity CLI (agy) - Issue #{issue_num} [{clean_model} / {clean_effort}]"
                launcher_path = Path(cwd_dir) / ".agy_terminal_launch.ps1"
                target_prompt = initial_prompt if is_continuation else agy_prompt
                safe_prompt = target_prompt.replace('@"', '`@"').replace('"@', '`"@')
                continue_flag = "--continue" if is_continuation else ""

                script_lines = [
                    "$OutputEncoding = [System.Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()",
                    f"$host.ui.RawUI.WindowTitle = '{title_str}'",
                    f"Write-Host '🚀 Launching Antigravity CLI for Issue #{issue_num} [{clean_model}]...' -ForegroundColor Cyan",
                    "$promptText = @\"",
                    safe_prompt,
                    "\"@",
                    f"& \"{AGY_CLI_PATH}\" {' '.join(cli_model_args)} {continue_flag} --dangerously-skip-permissions -i $promptText"
                ]
                launcher_path.write_text("\n".join(script_lines), encoding="utf-8")
                session.terminal_command = f'& "{AGY_CLI_PATH}" {" ".join(cli_model_args)} {continue_flag} --dangerously-skip-permissions -i "{target_prompt[:80]}..."'

                await self._append_message(
                    session_id,
                    MessageRole.SYSTEM,
                    f"🚀 [Option 1: Interactive Desktop Terminal] Spawning Antigravity CLI session in dedicated PowerShell window at: {cwd_dir}\n"
                    f"Model: {clean_model} • Effort: {clean_effort}"
                )
                from datetime import datetime
                session.last_activity_at = datetime.utcnow().isoformat()
                self._save()
                await self.broadcast("session_updated", session.model_dump())

                creation_flags = 0x00000010  # subprocess.CREATE_NEW_CONSOLE
                proc = subprocess.Popen(
                    ["powershell.exe", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", str(launcher_path)],
                    cwd=str(cwd_dir),
                    creationflags=creation_flags
                )
                self._active_agents[session_id] = proc

                # Keep session alive and interactive in review mode
                session.status = AgentStatus.IN_REVIEW
                self._save()
                await self.broadcast("session_updated", session.model_dump())
                return

            # Option 2: Live Stream into Web Dashboard (Override)
            else:
                prompt_note = f"Prompting agent with model {clean_model} (effort: {clean_effort})" if is_continuation else f"Spawning agent with model {clean_model} (effort: {clean_effort})"
                await self._append_message(
                    session_id,
                    MessageRole.SYSTEM,
                    f"🌐 [Option 2: Web Stream Override] {prompt_note} and streaming thoughts and tool calls live into this dashboard..."
                )
                self._save()
                await self.broadcast("session_updated", session.model_dump())

                cmd_args = [
                    str(AGY_CLI_PATH),
                    *cli_model_args,
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

                            from datetime import datetime
                            session.last_activity_at = datetime.utcnow().isoformat()
                            session.is_stalled = False

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
                                session.max_tokens = current_max_tokens
                                session.quota_percent = min(100.0, round((session.total_tokens / current_max_tokens) * 100, 1))

                                # TOKEN LIMIT GUARDRAIL
                                if getattr(config, "GUARDRAILS_ENABLED", True) and session.total_tokens >= current_max_tokens:
                                    session.status = AgentStatus.PAUSED
                                    session.error_message = f"Token budget limit reached ({session.total_tokens:,} / {current_max_tokens:,} tokens)."
                                    await self._append_message(
                                        session_id,
                                        MessageRole.SYSTEM,
                                        f"⚠️ [Token Budget Guardrail] Reached 100% of session quota ({session.total_tokens:,} tokens). "
                                        f"Agent execution safely paused without losing work. All changes in {cwd_dir} preserved. "
                                        f"You can click 'Resume' or raise your limit in Settings."
                                    )
                                    if proc.returncode is None:
                                        proc.terminate()
                                    self._save()
                                    await self.broadcast("session_updated", session.model_dump())
                                    return

                                self._save()
                                await self.broadcast("session_updated", session.model_dump())

                            if "duration_seconds" in step:
                                session.duration_seconds = step.get("duration_seconds", session.duration_seconds)

                            if stype == "tool":
                                tname = step.get("tool_name", "tool")
                                tinfo = step.get("tool_info", {})
                                if sstate == "ACTIVE":
                                    tparams = tinfo.get("parameters") or {}
                                    title_text, desc_text = format_tool_display(tname, tparams)
                                    session.current_activity = f"Executing: {title_text}"
                                    await self._append_message(
                                        session_id,
                                        MessageRole.TOOL_CALL,
                                        f"{title_text}\n{desc_text}".strip(),
                                        tool_name=tname,
                                        tool_args=tparams
                                    )

                                    # Normalized tool signature for duplicate detection
                                    clean_args = {k: v for k, v in tparams.items() if k not in ("toolAction", "toolSummary")}
                                    tool_sig = f"{tname}:{json.dumps(clean_args, sort_keys=True)}"

                                    # 1. CIRCUIT BREAKER: Duplicate Consecutive Tool Call Check
                                    if session.last_tool_signature == tool_sig:
                                        session.consecutive_duplicate_tool_count += 1
                                    else:
                                        session.last_tool_signature = tool_sig
                                        session.consecutive_duplicate_tool_count = 1

                                    dup_threshold = getattr(config, "CIRCUIT_BREAKER_DUPLICATE_THRESHOLD", 3)
                                    if getattr(config, "GUARDRAILS_ENABLED", True) and session.consecutive_duplicate_tool_count >= dup_threshold:
                                        logger.warning(
                                            f"[Circuit Breaker] Repetitive tool loop detected for session {session_id}: "
                                            f"'{tname}' executed {session.consecutive_duplicate_tool_count} consecutive times with identical arguments."
                                        )
                                        session.status = AgentStatus.PAUSED
                                        session.circuit_breaker_triggered = True
                                        session.error_message = (
                                            f"Circuit Breaker Triggered: Repetitive tool loop detected. "
                                            f"'{tname}' was called {session.consecutive_duplicate_tool_count} consecutive times with identical arguments."
                                        )
                                        if proc.returncode is None:
                                            try:
                                                proc.terminate()
                                            except Exception:
                                                pass

                                        await self._append_message(
                                            session_id,
                                            MessageRole.SYSTEM,
                                            f"🛑 **[Circuit Breaker Triggered: Repetitive Tool Loop]**\n\n"
                                            f"The agent repeatedly called `{tname}` with identical arguments without making progress:\n"
                                            f"```json\n{json.dumps(clean_args, indent=2)}\n```\n"
                                            f"Execution has been safely paused to prevent runaway token spend. "
                                            f"All worktree files at `{cwd_dir}` are preserved. Review the work and click 'Resume' or provide new instructions."
                                        )

                                        if session.issue_number and session.repo:
                                            try:
                                                pause_body = (
                                                    f"⚠️ **Task Paused: Circuit Breaker Triggered**\n\n"
                                                    f"### 🛑 Repetitive Tool Loop Detected\n"
                                                    f"- **Tool**: `{tname}` called {session.consecutive_duplicate_tool_count} consecutive times with identical arguments.\n"
                                                    f"- **Safeguard**: Execution halted immediately to prevent runaway token consumption.\n"
                                                    f"- **Worktree**: `{session.worktree_path or cwd_dir}`\n"
                                                    f"- **Status**: Paused awaiting developer review or resumption."
                                                )
                                                pause_comment = format_agent_comment(
                                                    body=pause_body,
                                                    header=BADGE_AGENT_PAUSED,
                                                    session_id=session.session_id,
                                                    worktree_path=session.worktree_path or cwd_dir,
                                                    git_branch=session.git_branch
                                                )
                                                comment_res = await post_issue_comment(session.repo, session.issue_number, pause_comment)
                                                if comment_res and "id" in comment_res:
                                                    session.seen_comment_ids.append(str(comment_res["id"]))
                                            except Exception as e:
                                                logger.warning(f"Could not post circuit breaker comment: {e}")

                                        self._save()
                                        await self.broadcast("session_updated", session.model_dump())
                                        return

                                    # 2. CIRCUIT BREAKER: Excessive Consecutive File Reads
                                    if tname == "view_file":
                                        session.consecutive_view_file_count += 1
                                    elif tname in ("replace_file_content", "write_to_file", "multi_replace_file_content", "run_command"):
                                        session.consecutive_view_file_count = 0

                                    max_reads_threshold = getattr(config, "CIRCUIT_BREAKER_MAX_CONSECUTIVE_READS", 8)
                                    if getattr(config, "GUARDRAILS_ENABLED", True) and session.consecutive_view_file_count >= max_reads_threshold:
                                        logger.warning(
                                            f"[Circuit Breaker] Excessive consecutive file reads for session {session_id}: "
                                            f"{session.consecutive_view_file_count} consecutive view_file calls without code edits or tests."
                                        )
                                        session.status = AgentStatus.PAUSED
                                        session.circuit_breaker_triggered = True
                                        session.error_message = (
                                            f"Circuit Breaker Triggered: Excessive consecutive file reads "
                                            f"({session.consecutive_view_file_count} view_file calls without editing code or running commands)."
                                        )
                                        if proc.returncode is None:
                                            try:
                                                proc.terminate()
                                            except Exception:
                                                pass

                                        await self._append_message(
                                            session_id,
                                            MessageRole.SYSTEM,
                                            f"🛑 **[Circuit Breaker Triggered: Excessive File Re-Reading]**\n\n"
                                            f"The agent performed {session.consecutive_view_file_count} consecutive `view_file` calls without making code edits or running tests.\n"
                                            f"Execution has been safely paused to prevent context saturation and token waste. "
                                            f"Click 'Resume' or provide specific guidance to proceed."
                                        )
                                        self._save()
                                        await self.broadcast("session_updated", session.model_dump())
                                        return

                                    # 3. TURN BUDGET GUARDRAIL (AGENTS.md Section 2: Max 15 Turns)
                                    max_turns_limit = getattr(config, "MAX_TURNS_PER_SESSION", 15)
                                    if getattr(config, "GUARDRAILS_ENABLED", True) and session.turn_count >= max_turns_limit:
                                        logger.warning(
                                            f"[Turn Budget Guardrail] Session {session_id} reached turn limit ({session.turn_count} / {max_turns_limit}). "
                                            "Pausing per AGENTS.md budget guardrail."
                                        )
                                        session.status = AgentStatus.PAUSED
                                        session.error_message = f"Turn Budget Limit reached ({session.turn_count} / {max_turns_limit} turns)."
                                        if proc.returncode is None:
                                            try:
                                                proc.terminate()
                                            except Exception:
                                                pass

                                        await self._append_message(
                                            session_id,
                                            MessageRole.SYSTEM,
                                            f"⚠️ **[Turn Budget Guardrail Reached]**\n\n"
                                            f"The agent has reached the maximum budget of **{max_turns_limit} tool execution turns** without completing the task.\n"
                                            f"Per **AGENTS.md Section 2**, execution is paused to prevent runaway token spend. "
                                            f"Worktree changes at `{cwd_dir}` are preserved. Review progress and click 'Resume' or provide follow-up instructions."
                                        )

                                        if session.issue_number and session.repo:
                                            try:
                                                pause_body = (
                                                    f"⚠️ **Task Paused: Token / Complexity Budget Threshold Reached**\n\n"
                                                    f"### 📊 Task Insights\n"
                                                    f"- **Turns Completed**: {session.turn_count} / {max_turns_limit}\n"
                                                    f"- **Tokens Recorded**: {session.token_count:,} tokens\n"
                                                    f"- **Worktree**: `{session.worktree_path or cwd_dir}`\n"
                                                    f"- **Status**: Paused per AGENTS.md Turn Limit Guardrail (Max {max_turns_limit} turns).\n"
                                                    f"- **Proposed Next Action**: Review work in worktree and approve continuation from Agent Manager UI or add instructions."
                                                )
                                                pause_comment = format_agent_comment(
                                                    body=pause_body,
                                                    header=BADGE_AGENT_PAUSED,
                                                    session_id=session.session_id,
                                                    worktree_path=session.worktree_path or cwd_dir,
                                                    git_branch=session.git_branch
                                                )
                                                comment_res = await post_issue_comment(session.repo, session.issue_number, pause_comment)
                                                if comment_res and "id" in comment_res:
                                                    session.seen_comment_ids.append(str(comment_res["id"]))
                                            except Exception as e:
                                                logger.warning(f"Could not post turn budget comment: {e}")

                                        self._save()
                                        await self.broadcast("session_updated", session.model_dump())
                                        return
                                elif sstate == "DONE":
                                    raw_out = tinfo.get("output", "")
                                    tparams = tinfo.get("parameters") or {}
                                    if tname == "run_command":
                                        result_content = format_command_output(tname, raw_out, tparams)
                                    else:
                                        out_str = str(raw_out) if raw_out is not None else ""
                                        if out_str.strip() and out_str.strip() != "Done":
                                            result_content = out_str
                                        else:
                                            title_text, _ = format_tool_display(tname, tparams)
                                            result_content = f"Completed: {title_text}"
                                    await self._append_message(
                                        session_id,
                                        MessageRole.TOOL_RESULT,
                                        result_content,
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
                            # CRITICAL: Chat stays open and active in IN_REVIEW until issue is moved to Done!
                            session.status = AgentStatus.IN_REVIEW
                            await self._append_message(
                                session_id,
                                MessageRole.SYSTEM,
                                "💬 [Turn Complete] Agent finished this execution turn. The chat remains open and active for follow-up questions, instructions, or reviews until this issue is moved to 'Done' on the Project Board."
                            )
                            self._save()
                            await self.broadcast("session_updated", session.model_dump())

                            # Automatically post agent response as a comment on the GitHub issue
                            if session.issue_number and session.repo:
                                try:
                                    comment_content = format_agent_comment(
                                        body=final_resp.strip(),
                                        header=BADGE_AGENT_UPDATE,
                                        session_id=session.session_id,
                                        worktree_path=session.worktree_path,
                                        git_branch=session.git_branch
                                    )
                                    comment_res = await post_issue_comment(session.repo, session.issue_number, comment_content)
                                    if comment_res and "id" in comment_res:
                                        session.seen_comment_ids.append(str(comment_res["id"]))
                                        self._save()
                                except Exception as post_err:
                                    logger.error(f"Failed to post agent completion comment to GitHub: {post_err}")
                        elif ev == "error" or event_obj.get("error"):
                            err_txt = json.dumps(event_obj.get("error", event_obj))
                            if _looks_like_quota_error(err_txt):
                                await self._flag_quota_exceeded(session_id, err_txt)
                    except json.JSONDecodeError:
                        if _looks_like_quota_error(line_str):
                            await self._flag_quota_exceeded(session_id, line_str)
                    except Exception as json_err:
                        logger.debug(f"JSON stream line parse info: {json_err}")

                await proc.wait()
                try:
                    stderr_txt = (await proc.stderr.read()).decode("utf-8", errors="replace")
                except Exception:
                    stderr_txt = ""
                if proc.returncode != 0 and _looks_like_quota_error(stderr_txt):
                    await self._flag_quota_exceeded(session_id, stderr_txt)
                if proc.returncode != 0 and stderr_txt.strip():
                    await self._append_message(session_id, MessageRole.SYSTEM, f"Agent CLI exited with code {proc.returncode}: {stderr_txt.strip()[-800:]}")
                
                try:
                    from agent_manager.telemetry import record_token_usage
                    record_token_usage(
                        session_id=session_id,
                        repo=session.repo or "",
                        model=session.model or clean_model,
                        input_tokens=session.input_tokens,
                        output_tokens=session.output_tokens,
                        thinking_tokens=session.thinking_tokens,
                        cache_read_tokens=session.cache_read_tokens,
                        total_tokens=session.total_tokens
                    )
                except Exception as tel_err:
                    logger.debug(f"Telemetry record error in agent loop: {tel_err}")

                if session.status not in [AgentStatus.PAUSED, AgentStatus.STOPPED, AgentStatus.COMPLETED]:
                    session.status = AgentStatus.IN_REVIEW if proc.returncode == 0 else AgentStatus.FAILED
                
                # Automatically compact / compress chat when process finishes successfully
                if proc.returncode == 0 and session.status != AgentStatus.FAILED:
                    await self.compact_session(session_id)
                    
                    if getattr(config, "AUTO_MERGE_ENABLED", False) and session.repo and session.git_branch:
                        try:
                            from agent_manager.github import find_pr_for_branch, merge_pull_request
                            pr_num = await find_pr_for_branch(session.repo, session.git_branch)
                            if pr_num:
                                logger.info(f"Auto-merging PR #{pr_num} for session {session_id} since it's IN_REVIEW.")
                                res = await merge_pull_request(session.repo, pr_num)
                                if res:
                                    from agent_manager.poller import LocalGitWatcher
                                    watcher = LocalGitWatcher()
                                    if session.issue_number:
                                        await watcher.update_issue_status(session.repo, session.issue_number, "done")
                                    await self.complete_agent(session_id, reason="Auto-merged PR and marked as Done")
                        except Exception as e:
                            logger.error(f"Failed to auto-merge PR or mark issue as done: {e}")

                self._save()
                await self.broadcast("session_updated", session.model_dump())
                return
        except asyncio.CancelledError:
            if session.status != AgentStatus.COMPLETED:
                session.status = AgentStatus.STOPPED
            logger.info(f"Agent session {session_id} task was cancelled.")
        except Exception as e:
            session.status = AgentStatus.FAILED
            session.error_message = str(e)
            logger.exception(f"Error during agent session {session_id}: {e}")
            await self._append_message(session_id, MessageRole.SYSTEM, f"Agent encountered error: {str(e)}")
        finally:
            curr_mode = getattr(config, "AGY_MODE", AGY_MODE)
            if curr_mode != "terminal":
                self._active_agents.pop(session_id, None)
            self._save()
            await self.broadcast("session_updated", session.model_dump())

    async def start_watchdog(self):
        """Monitors active sessions for hangs or long-running stalled tool executions."""
        while True:
            try:
                await asyncio.sleep(5)
                from datetime import datetime
                now = datetime.utcnow()
                for sid, s in list(self.sessions.items()):
                    if s.status == AgentStatus.RUNNING:
                        if s.last_activity_at:
                            try:
                                last_time = datetime.fromisoformat(s.last_activity_at)
                                elapsed = (now - last_time).total_seconds()
                                if elapsed > 30 and not s.is_stalled:
                                    s.is_stalled = True
                                    act_name = s.current_activity or "tool execution"
                                    s.current_activity = f"⚠️ Unresponsive / Hung on {act_name} ({int(elapsed)}s without output)"
                                    self._save()
                                    await self.broadcast("session_updated", s.model_dump())
                            except Exception:
                                pass

                    # Server-side idle timeout management (only when running in server mode)
                    is_srv = getattr(config, "IS_SERVER", IS_SERVER)
                    if is_srv and s.status in [AgentStatus.RUNNING, AgentStatus.IN_REVIEW]:
                        timeout_mins = getattr(config, "CLI_IDLE_TIMEOUT_MINUTES", CLI_IDLE_TIMEOUT_MINUTES)
                        timeout_secs = timeout_mins * 60
                        if s.last_activity_at:
                            try:
                                last_active = datetime.fromisoformat(s.last_activity_at)
                                idle_elapsed = (now - last_active).total_seconds()
                                if idle_elapsed > timeout_secs:
                                    proc = self._active_agents.get(sid)
                                    if proc is not None:
                                        logger.info(f"Session {sid} exceeded idle timeout of {timeout_mins}m on server. Closing CLI instance.")
                                        if hasattr(proc, 'terminate'):
                                            try:
                                                proc.terminate()
                                            except Exception:
                                                pass
                                        self._active_agents.pop(sid, None)
                                        s.status = AgentStatus.IDLE
                                        s.current_activity = f"💤 Idle CLI instance closed after {timeout_mins}m inactivity."
                                        await self._append_message(
                                            sid,
                                            MessageRole.SYSTEM,
                                            f"💤 [Server Idle Timeout] CLI terminal automatically closed after {timeout_mins} minutes of inactivity to preserve server resources."
                                        )
                                        self._save()
                                        await self.broadcast("session_updated", s.model_dump())
                            except Exception:
                                pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in runner watchdog: {e}")

    async def interrupt_agent(self, session_id: str) -> bool:
        """Interrupts a running or hanging agent execution and leaves it ready for new instructions."""
        session = self.sessions.get(session_id)
        if not session:
            return False

        proc = self._active_agents.get(session_id)
        if proc and hasattr(proc, 'terminate'):
            try:
                proc.terminate()
            except Exception:
                pass
            self._active_agents.pop(session_id, None)

        task = self._tasks.get(session_id)
        if task and not task.done():
            task.cancel()

        session.status = AgentStatus.IN_REVIEW
        session.is_stalled = False
        session.current_activity = "Interrupted by user. Ready for new input."
        msg = ConversationMessage(
            id=str(uuid.uuid4()),
            role=MessageRole.SYSTEM,
            content="⏹️ [Agent Execution Interrupted] Process halted safely. Chat remains open and waiting for your instructions."
        )
        session.messages.append(msg)
        self._save()
        await self.broadcast("session_updated", session.model_dump())
        logger.info(f"Agent session {session_id} manually interrupted.")
        return True

    async def _flag_quota_exceeded(self, session_id: str, detail: str):
        """Pauses the session and raises a prominent quota alert in the dashboard."""
        session = self.sessions.get(session_id)
        if not session or session.quota_exceeded:
            return
        session.status = AgentStatus.PAUSED
        session.quota_exceeded = True
        session.is_stalled = False
        session.quota_message = detail.strip()[:500] or "Model quota / rate limit reached."
        session.current_activity = "🚫 Quota limit reached"
        session.error_message = session.quota_message
        await self._append_message(
            session_id, MessageRole.SYSTEM,
            f"🚫 [Quota Limit Reached] The model provider rejected the request: {session.quota_message}\n"
            f"Work in {session.worktree_path or 'the workspace'} is preserved. Switch to a different model in Settings "
            f"or wait for the quota window to reset, then click 'Resume'."
        )
        self._save()
        await self.broadcast("quota_alert", {
            "session_id": session_id,
            "title": session.title,
            "issue_number": session.issue_number,
            "repo": session.repo,
            "message": session.quota_message,
        })
        await self.broadcast("session_updated", session.model_dump())
        logger.warning(f"Quota limit reached for session {session_id}: {session.quota_message}")
