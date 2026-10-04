import uuid
import asyncio
from agent_manager.models import (
    SpawnRequest, AgentSessionInfo, AgentStatus, MessageRole,
    ConversationMessage, WorkflowStage
)
import agent_manager.config as config
from agent_manager.config import DEFAULT_REPO
from agent_manager.runners.worktree_manager import setup_worktree


async def spawn_agent(manager, req: SpawnRequest) -> AgentSessionInfo:
    repo = req.repo or DEFAULT_REPO
    issue_number = req.issue_number

    if issue_number:
        existing = [
            s for s in manager.sessions.values()
            if s.repo == repo and s.issue_number == issue_number and s.status in [AgentStatus.RUNNING, AgentStatus.INITIALIZING, AgentStatus.PAUSED]
        ]
        if existing:
            return existing[0]

    session_id = f"issue-{issue_number}-{uuid.uuid4().hex}" if issue_number else str(uuid.uuid4())
    worktree_path = None
    branch_name = None
    if issue_number:
        worktree_path, branch_name = setup_worktree(repo, issue_number)

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
    manager.sessions[session_id] = session
    manager._context_queues[session_id] = asyncio.Queue()

    initial_msg = ConversationMessage(
        id=str(uuid.uuid4()),
        role=MessageRole.USER,
        content=req.prompt
    )
    session.messages.append(initial_msg)
    manager._save()
    await manager.broadcast("session_created", session.model_dump())

    task = asyncio.create_task(manager._run_agent_loop(session_id, req.prompt, worktree_path))
    manager._tasks[session_id] = task
    return session


async def restart_agent(manager, session_id: str) -> AgentSessionInfo:
    session = manager.sessions.get(session_id)
    if not session:
        return None

    await manager.stop_agent(session_id, reason="Restarted by user")

    session.status = AgentStatus.INITIALIZING
    session.error_message = None
    session.turn_count = 0
    session.consecutive_duplicate_tool_count = 0
    session.consecutive_view_file_count = 0
    session.last_tool_signature = None
    session.circuit_breaker_triggered = False
    session.model = getattr(config, "DEFAULT_MODEL", session.model or "gemini-3.8-flash")
    session.effort = getattr(config, "DEFAULT_EFFORT", session.effort or "high")

    restart_msg = ConversationMessage(
        id=str(uuid.uuid4()),
        role=MessageRole.SYSTEM,
        content=f"🔄 Agent session restarted with model: {session.model} (effort: {session.effort})."
    )
    session.messages.append(restart_msg)
    manager._save()
    await manager.broadcast("session_updated", session.model_dump())

    manager._context_queues[session_id] = asyncio.Queue()
    initial_prompt = session.messages[0].content if session.messages else f"Execute task for issue #{session.issue_number}"
    task = asyncio.create_task(manager._run_agent_loop(session_id, initial_prompt, session.worktree_path))
    manager._tasks[session_id] = task
    return session


async def resume_agent(manager, session_id: str) -> bool:
    session = manager.sessions.get(session_id)
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
    session.model = getattr(config, "DEFAULT_MODEL", session.model or "gemini-3.8-flash")
    session.effort = getattr(config, "DEFAULT_EFFORT", session.effort or "high")

    resume_msg = ConversationMessage(
        id=str(uuid.uuid4()),
        role=MessageRole.SYSTEM,
        content=f"▶️ Session resumed by user with model: {session.model} (effort: {session.effort}). Continuing execution in isolated worktree."
    )
    session.messages.append(resume_msg)
    manager._save()
    await manager.broadcast("session_updated", session.model_dump())

    task = asyncio.create_task(
        manager._run_agent_loop(session_id, "Continue working on the task and conclude your remaining deliverables.", session.worktree_path, is_continuation=True)
    )
    manager._tasks[session_id] = task
    return True
