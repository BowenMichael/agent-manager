import asyncio
import logging
import uuid
from datetime import datetime
from agent_manager.models import AgentStatus, ConversationMessage, MessageRole
import agent_manager.config as config
from agent_manager.config import IS_SERVER, CLI_IDLE_TIMEOUT_MINUTES

logger = logging.getLogger("agent_manager.runners.watchdog")


async def start_watchdog(manager):
    """Monitors active sessions for hangs or long-running stalled tool executions."""
    while True:
        try:
            await asyncio.sleep(5)
            now = datetime.utcnow()
            for sid, s in list(manager.sessions.items()):
                if s.status == AgentStatus.RUNNING:
                    if s.last_activity_at:
                        try:
                            last_time = datetime.fromisoformat(s.last_activity_at)
                            elapsed = (now - last_time).total_seconds()
                            if elapsed > 30 and not s.is_stalled:
                                s.is_stalled = True
                                act_name = s.current_activity or "tool execution"
                                s.current_activity = f"⚠️ Unresponsive / Hung on {act_name} ({int(elapsed)}s without output)"
                                manager._save()
                                await manager.broadcast("session_updated", s.model_dump())
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
                                proc = manager._active_agents.get(sid)
                                if proc is not None:
                                    logger.info(f"Session {sid} exceeded idle timeout of {timeout_mins}m on server. Closing CLI instance.")
                                    if hasattr(proc, 'terminate'):
                                        try:
                                            proc.terminate()
                                        except Exception:
                                            pass
                                    manager._active_agents.pop(sid, None)
                                    s.status = AgentStatus.IDLE
                                    s.current_activity = f"💤 Idle CLI instance closed after {timeout_mins}m inactivity."
                                    await manager._append_message(
                                        sid,
                                        MessageRole.SYSTEM,
                                        f"💤 [Server Idle Timeout] CLI terminal automatically closed after {timeout_mins} minutes of inactivity to preserve server resources."
                                    )
                                    manager._save()
                                    await manager.broadcast("session_updated", s.model_dump())
                        except Exception:
                            pass
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in runner watchdog: {e}")


async def interrupt_agent(manager, session_id: str) -> bool:
    session = manager.sessions.get(session_id)
    if not session:
        return False

    proc = manager._active_agents.get(session_id)
    if proc and hasattr(proc, 'terminate'):
        try:
            proc.terminate()
        except Exception:
            pass
        manager._active_agents.pop(session_id, None)

    task = manager._tasks.get(session_id)
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
    manager._save()
    await manager.broadcast("session_updated", session.model_dump())
    logger.info(f"Agent session {session_id} manually interrupted.")
    return True


async def flag_quota_exceeded(manager, session_id: str, detail: str):
    session = manager.sessions.get(session_id)
    if not session or session.quota_exceeded:
        return
    session.status = AgentStatus.PAUSED
    session.quota_exceeded = True
    session.is_stalled = False
    session.quota_message = detail.strip()[:500] or "Model quota / rate limit reached."
    session.current_activity = "🚫 Quota limit reached"
    session.error_message = session.quota_message
    await manager._append_message(
        session_id, MessageRole.SYSTEM,
        f"🚫 [Quota Limit Reached] The model provider rejected the request: {session.quota_message}\n"
        f"Work in {session.worktree_path or 'the workspace'} is preserved. Switch to a different model in Settings "
        f"or wait for the quota window to reset, then click 'Resume'."
    )
    manager._save()
    await manager.broadcast("quota_alert", {
        "session_id": session_id,
        "title": session.title,
        "issue_number": session.issue_number,
        "repo": session.repo,
        "message": session.quota_message,
    })
    await manager.broadcast("session_updated", session.model_dump())
    logger.warning(f"Quota limit reached for session {session_id}: {session.quota_message}")
