import uuid
import json
import asyncio
import logging
from typing import Dict, List, Optional
from fastapi import WebSocket

import agent_manager.config as config
from agent_manager.models import (
    AgentSessionInfo, AgentStatus, ConversationMessage,
    MessageRole, SpawnRequest
)
from agent_manager.storage import save_sessions, load_sessions
from agent_manager.github import post_issue_comment
from agent_manager.runners.helpers import (
    format_tool_display, get_repository_context, looks_like_quota_error
)
from agent_manager.runners.worktree_manager import setup_worktree
from agent_manager.runners.lifecycle import (
    stop_agent, compact_session, complete_agent,
    archive_agent, unarchive_agent, delete_agent
)
from agent_manager.runners.watchdog import (
    start_watchdog, interrupt_agent, flag_quota_exceeded
)
from agent_manager.runners.spawner import (
    spawn_agent, restart_agent, resume_agent
)
from agent_manager.runners.pipeline import run_workflow_pipeline
from agent_manager.runners.cli_turn import run_cli_turn
from agent_manager.runners.orchestrator import run_agent_loop
from agent_manager.runners.process_manager import is_process_alive, terminate_process
from agent_manager.runners.stream_tailer import tail_agent_log

logger = logging.getLogger("agent_manager.runner")



class AgentRunnerManager:
    _instance: Optional["AgentRunnerManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_manager()
        return cls._instance

    def _init_manager(self):
        self._watchdog_task = None
        self.sessions: Dict[str, AgentSessionInfo] = load_sessions()
        self._active_agents: Dict[str, asyncio.subprocess.Process] = {}
        self._context_queues: Dict[str, asyncio.Queue] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._ws_connections: List[WebSocket] = []

        for sid in self.sessions:
            self._context_queues[sid] = asyncio.Queue()

    def reattach_active_sessions(self):
        """Discovers and reattaches to running background agent processes on server startup."""
        self.sessions = load_sessions()
        for sid, s in self.sessions.items():
            if s.status == AgentStatus.RUNNING and s.pid:
                if is_process_alive(s.pid):
                    logger.info(f"Reattaching to active detached agent session {sid} (PID: {s.pid})")
                    task = asyncio.create_task(tail_agent_log(self, sid, clean_model=s.model or ""))
                    self._tasks[sid] = task
                else:
                    logger.info(f"Detached agent session {sid} (PID: {s.pid}) is no longer active; draining remaining output.")
                    task = asyncio.create_task(tail_agent_log(self, sid, clean_model=s.model or ""))
                    self._tasks[sid] = task

    def _save(self):
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
        return setup_worktree(repo, issue_number)

    async def spawn_agent(self, req: SpawnRequest, defer_start: bool = False) -> AgentSessionInfo:
        return await spawn_agent(self, req, defer_start=defer_start)

    async def restart_agent(self, session_id: str) -> Optional[AgentSessionInfo]:
        return await restart_agent(self, session_id)

    async def resume_agent(self, session_id: str) -> bool:
        return await resume_agent(self, session_id)

    async def stop_agent(self, session_id: str, reason: str = "Stopped by user") -> bool:
        return await stop_agent(self, session_id, reason)

    async def compact_session(self, session_id: str, force: bool = False) -> bool:
        return await compact_session(self, session_id, force)

    async def complete_agent(self, session_id: str, reason: str = "Issue moved to 'Done' on Project Board") -> bool:
        return await complete_agent(self, session_id, reason)

    async def archive_agent(self, session_id: str) -> bool:
        return await archive_agent(self, session_id)

    async def unarchive_agent(self, session_id: str) -> bool:
        return await unarchive_agent(self, session_id)

    async def delete_agent(self, session_id: str) -> bool:
        return await delete_agent(self, session_id)

    async def start_watchdog(self):
        await start_watchdog(self)

    async def interrupt_agent(self, session_id: str) -> bool:
        return await interrupt_agent(self, session_id)

    async def _flag_quota_exceeded(self, session_id: str, detail: str):
        await flag_quota_exceeded(self, session_id, detail)

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

    async def _broadcast_token(self, session_id: str, token: str):
        session = self.sessions[session_id]
        session.token_count += 1
        await self.broadcast("token_stream", {"session_id": session_id, "token": token})

    async def _run_cli_turn(self, session_id: str, prompt: str, cwd_dir: str, model: str, effort: str) -> str:
        return await run_cli_turn(self, session_id, prompt, cwd_dir, model, effort)

    async def _run_workflow_pipeline(self, session_id: str, task_description: str, cwd_dir: str, issue_num: int, branch_name: str):
        await run_workflow_pipeline(self, session_id, task_description, cwd_dir, issue_num, branch_name)

    async def _run_agent_loop(self, session_id: str, initial_prompt: str, worktree_path: Optional[str], is_continuation: bool = False):
        await run_agent_loop(self, session_id, initial_prompt, worktree_path, is_continuation=is_continuation)

    async def add_context(self, session_id: str, context: str) -> bool:
        session = self.sessions.get(session_id)
        if not session:
            return False

        user_msg = ConversationMessage(id=str(uuid.uuid4()), role=MessageRole.USER, content=context)
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

        current_cfg_model = getattr(config, "DEFAULT_MODEL", "gemini-3.8-flash")
        current_cfg_effort = getattr(config, "DEFAULT_EFFORT", "high")
        if session.model != current_cfg_model or session.effort != current_cfg_effort:
            session.model = current_cfg_model
            session.effort = current_cfg_effort

        self._save()
        await self.broadcast("message_added", {"session_id": session_id, "message": user_msg.model_dump()})

        queue = self._context_queues.get(session_id)
        if queue:
            await queue.put(context)

        current_mode = getattr(config, "AGY_MODE", "terminal")
        proc = self._active_agents.get(session_id)
        if current_mode != "terminal" and proc and hasattr(proc, 'terminate'):
            try:
                proc.terminate()
            except Exception:
                pass
            self._active_agents.pop(session_id, None)

        if current_mode != "terminal" and session.pid:
            try:
                terminate_process(session.pid)
            except Exception:
                pass

        task = self._tasks.get(session_id)
        if task and not task.done():
            task.cancel()

        session.status = AgentStatus.RUNNING
        session.error_message = None
        self._save()
        await self.broadcast("session_updated", session.model_dump())

        new_task = asyncio.create_task(
            self._run_agent_loop(session_id, context, session.worktree_path, is_continuation=True)
        )
        self._tasks[session_id] = new_task
        return True
