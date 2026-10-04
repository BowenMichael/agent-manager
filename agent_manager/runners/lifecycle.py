import uuid
import logging
from datetime import datetime
from typing import List, Optional
from agent_manager.models import (
    ConversationMessage, MessageRole, AgentStatus
)
import agent_manager.config as config
from agent_manager.config import COMPACT_COMPLETED_CHAT
from agent_manager.runners.process_manager import terminate_process
from agent_manager.services.dispatch_trigger import fire_dispatch_hook

logger = logging.getLogger("agent_manager.runners.lifecycle")


async def stop_agent(manager, session_id: str, reason: str = "Stopped by user") -> bool:
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

    if session.pid:
        try:
            terminate_process(session.pid)
        except Exception:
            pass

    task = manager._tasks.get(session_id)
    if task and not task.done():
        task.cancel()

    session.status = AgentStatus.STOPPED
    stop_msg = ConversationMessage(
        id=str(uuid.uuid4()),
        role=MessageRole.SYSTEM,
        content=f"⏹️ Agent stopped. Reason: {reason}"
    )
    session.messages.append(stop_msg)
    manager._save()
    await manager.broadcast("session_updated", session.model_dump())
    logger.info(f"Agent {session_id} stopped: {reason}")
    fire_dispatch_hook()
    return True


async def compact_session(manager, session_id: str, force: bool = False) -> bool:
    session = manager.sessions.get(session_id)
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

    if len(original_msgs) <= 3 and tool_call_count == 0:
        session.is_compacted = True
        manager._save()
        return True

    tools_used = set()
    for m in original_msgs:
        if m.tool_name:
            tools_used.add(m.tool_name)
        elif m.role == MessageRole.TOOL_CALL and m.tool_name:
            tools_used.add(m.tool_name)

    compacted_summary_lines = [
        f"📦 **Chat Compacted & Compressed (Token Optimization)**",
        f"- **Execution Summary**: Completed {tool_call_count} tool actions ({', '.join(sorted(tools_used)) if tools_used else 'direct execution'}).",
        f"- **Compressed Artifacts**: Compacted {tool_call_count + tool_result_count} tool messages and {thought_count} thought traces.",
        f"- **Tokens Recorded**: {session.total_tokens:,} tokens ({session.input_tokens:,} input / {session.output_tokens:,} output / {session.thinking_tokens:,} reasoning)."
    ]
    summary_text = "\n".join(compacted_summary_lines)

    new_messages: List[ConversationMessage] = []
    if user_msgs:
        new_messages.append(user_msgs[0])

    new_messages.append(ConversationMessage(
        id=str(uuid.uuid4()),
        role=MessageRole.SYSTEM,
        content=summary_text
    ))

    if len(user_msgs) > 1:
        for extra_user_msg in user_msgs[1:]:
            new_messages.append(extra_user_msg)

    if agent_msgs:
        new_messages.append(agent_msgs[-1])

    session.messages = new_messages
    session.is_compacted = True
    session.compact_summary = summary_text
    manager._save()
    await manager.broadcast("session_updated", session.model_dump())
    logger.info(f"Agent session {session_id} chat transcript compacted successfully ({len(original_msgs)} -> {len(new_messages)} messages).")
    return True


async def complete_agent(manager, session_id: str, reason: str = "Issue moved to 'Done' on Project Board") -> bool:
    session = manager.sessions.get(session_id)
    if not session:
        return False

    proc = manager._active_agents.get(session_id)
    if proc and hasattr(proc, 'terminate'):
        try:
            proc.terminate()
        except Exception:
            pass

    task = manager._tasks.get(session_id)
    if task and not task.done():
        task.cancel()

    session.status = AgentStatus.COMPLETED
    complete_msg = ConversationMessage(
        id=str(uuid.uuid4()),
        role=MessageRole.SYSTEM,
        content=f"✅ [Task Completed & Archived] {reason}. Chat session has concluded successfully."
    )
    session.messages.append(complete_msg)
    await compact_session(manager, session_id)

    manager._save()
    await manager.broadcast("session_updated", session.model_dump())
    logger.info(f"Agent {session_id} completed: {reason}")
    fire_dispatch_hook()
    return True


async def archive_agent(manager, session_id: str) -> bool:
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

    session.is_archived = True
    session.archived_at = datetime.utcnow().isoformat()
    if session.status in [AgentStatus.RUNNING, AgentStatus.INITIALIZING]:
        session.status = AgentStatus.STOPPED

    archive_msg = ConversationMessage(
        id=str(uuid.uuid4()),
        role=MessageRole.SYSTEM,
        content="📦 [Agent Archived] This agent session has been archived."
    )
    session.messages.append(archive_msg)
    manager._save()
    await manager.broadcast("session_updated", session.model_dump())
    logger.info(f"Agent {session_id} archived.")
    fire_dispatch_hook()
    return True


async def unarchive_agent(manager, session_id: str) -> bool:
    session = manager.sessions.get(session_id)
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
    manager._save()
    await manager.broadcast("session_updated", session.model_dump())
    logger.info(f"Agent {session_id} unarchived.")
    return True


async def delete_agent(manager, session_id: str) -> bool:
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

    manager.sessions.pop(session_id, None)
    manager._context_queues.pop(session_id, None)
    manager._save()
    await manager.broadcast("session_deleted", {"session_id": session_id})
    logger.info(f"Agent {session_id} deleted permanently.")
    return True
