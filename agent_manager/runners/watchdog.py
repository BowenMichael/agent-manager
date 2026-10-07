"""
Agent Watchdog & Liveness Monitor.
Tracks active sessions for hangs, stalled executions, quota limits, and idle timeouts.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import asyncio
import logging
from datetime import datetime, timezone
from agent_manager.models import AgentStatus, MessageRole
import agent_manager.config as config
from agent_manager.runners.process_manager import terminate_process, is_process_alive

logger = logging.getLogger("agent_manager.runners.watchdog")


async def _check_dead_process(manager, sid: str, s):
    """Detects if an agent process died unexpectedly and marks session failed."""
    if s.status != AgentStatus.RUNNING or not s.pid:
        return
    if not is_process_alive(s.pid):
        logger.warning(f"Agent session {sid} (PID {s.pid}) process terminated unexpectedly.")
        s.status = AgentStatus.FAILED
        s.error_message = f"Process {s.pid} terminated unexpectedly."
        s.is_stalled = False
        s.current_activity = "❌ Process terminated unexpectedly."
        manager._save()
        await manager.broadcast("session_updated", s.model_dump())


async def _check_stalled_agent(manager, s, now: datetime):
    """Detects if an active running agent has become unresponsive."""
    if not s.last_activity_at:
        return
    try:
        curr_now = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        last_time = datetime.fromisoformat(s.last_activity_at)
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
        elapsed = (curr_now - last_time).total_seconds()
        if elapsed > 30 and not s.is_stalled:
            s.is_stalled = True
            act_name = s.current_activity or "tool execution"
            s.current_activity = f"⚠️ Unresponsive / Hung on {act_name} ({int(elapsed)}s without output)"
            manager._save()
            await manager.broadcast("session_updated", s.model_dump())
    except Exception as e:
        logger.debug(f"Error evaluating stall on {s.session_id}: {e}")


async def _check_idle_timeout(manager, sid: str, s, now: datetime):
    """Closes idle CLI instances on the server to preserve cloud resources."""
    is_srv = getattr(config, "IS_SERVER", False)
    if not is_srv or s.status not in [AgentStatus.RUNNING, AgentStatus.IN_REVIEW]:
        return
    timeout_mins = getattr(config, "CLI_IDLE_TIMEOUT_MINUTES", 30)
    if not s.last_activity_at:
        return
    try:
        curr_now = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        last_active = datetime.fromisoformat(s.last_activity_at)
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)
        idle_elapsed = (curr_now - last_active).total_seconds()
        if idle_elapsed > (timeout_mins * 60):

            proc = manager._active_agents.pop(sid, None)
            if proc and hasattr(proc, 'terminate'):
                try: proc.terminate()
                except Exception: pass
            if s.pid:
                try: terminate_process(s.pid)
                except Exception: pass
            s.status = AgentStatus.IDLE
            s.current_activity = f"💤 Idle CLI instance closed after {timeout_mins}m inactivity."
            await manager._append_message(sid, MessageRole.SYSTEM, f"💤 [Server Idle Timeout] Closed after {timeout_mins}m inactivity.")
            manager._save()
            await manager.broadcast("session_updated", s.model_dump())
    except Exception as e:
        logger.debug(f"Error evaluating idle timeout on {sid}: {e}")


async def start_watchdog(manager):
    """Periodic watchdog monitor checking stall state, dead processes, and idle timeouts."""
    while True:
        try:
            await asyncio.sleep(5)
            now = datetime.now(timezone.utc)
            for sid, s in list(manager.sessions.items()):
                if s.status == AgentStatus.RUNNING:
                    await _check_dead_process(manager, sid, s)
                    await _check_stalled_agent(manager, s, now)
                await _check_idle_timeout(manager, sid, s, now)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in runner watchdog loop: {e}")



async def interrupt_agent(manager, session_id: str) -> bool:
    """Safely interrupts and terminates an active agent session."""
    session = manager.sessions.get(session_id)
    if not session:
        return False
    proc = manager._active_agents.pop(session_id, None)
    if proc and hasattr(proc, 'terminate'):
        try: proc.terminate()
        except Exception: pass
    if session.pid:
        try: terminate_process(session.pid)
        except Exception: pass
    task = manager._tasks.get(session_id)
    if task and not task.done():
        task.cancel()
    session.status = AgentStatus.IN_REVIEW
    session.is_stalled = False
    session.current_activity = "Interrupted by user. Ready for new input."
    manager._save()
    await manager.broadcast("session_updated", session.model_dump())
    return True


async def flag_quota_exceeded(manager, session_id: str, message: str):
    """Flags an agent session as rate-limited or quota-exceeded."""
    session = manager.sessions.get(session_id)
    if not session:
        return
    session.status = AgentStatus.PAUSED
    session.is_stalled = False
    session.current_activity = f"🛑 Quota / Rate Limit Exceeded: {message[:100]}"
    await manager._append_message(session_id, MessageRole.SYSTEM, f"🛑 [Quota Exceeded] {message}")
    manager._save()
    await manager.broadcast("session_updated", session.model_dump())
