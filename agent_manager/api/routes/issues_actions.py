import logging
import asyncio
from fastapi import APIRouter, HTTPException

from agent_manager.runner import AgentRunnerManager
from agent_manager.models import SpawnRequest, AgentStatus
from agent_manager.services.projects_aggregator import get_all_projects_data
from agent_manager.runners.supervisor import post_takeover_notice, sync_issue_board_status
from agent_manager.api.routes.issues_crud import IssueActionRequest

logger = logging.getLogger("agent_manager.api.routes.issues_actions")
router = APIRouter()
runner = AgentRunnerManager()


def _format_issue_prompt(repo: str, issue_number: int, title: str, body: str) -> str:
    return (
        f"You have been assigned to GitHub Issue #{issue_number} in {repo}.\n\n"
        f"**Title**: {title or f'Issue #{issue_number}'}\n\n"
        f"**Requirements / Description**:\n{body or 'Please resolve this issue.'}\n\n"
        f"**Directives**:\n"
        f"1. Work strictly in your isolated worktree.\n"
        f"2. Follow AGENTS.md modular anti-monolith guidelines.\n"
        f"3. MANDATORY: Update CHANGELOG.md with your changes before opening a PR or completing.\n"
        f"4. Run unit tests to verify before concluding."
    )


@router.post("/start")
async def start_issue_agent(req: IssueActionRequest):
    """Starts or resumes an agent to work on the specified issue in its isolated worktree."""
    try:
        existing = [
            s for s in runner.sessions.values()
            if s.repo == req.repo and s.issue_number == req.issue_number and s.status in [AgentStatus.RUNNING, AgentStatus.INITIALIZING, AgentStatus.PAUSED]
        ]
        if existing:
            active = existing[0]
            if active.status == AgentStatus.PAUSED:
                await runner.resume_agent(active.session_id)
            return {"status": "ok", "message": f"Agent resumed for Issue #{req.issue_number}", "session_id": active.session_id}

        title = req.title
        body = req.body
        if not title:
            data = await get_all_projects_data()
            for p in data.get("projects", []):
                for item in p.get("items", []):
                    if item.get("repo") == req.repo and item.get("number") == req.issue_number:
                        title = item.get("title")
                        body = item.get("body")
                        break

        prompt = _format_issue_prompt(req.repo, req.issue_number, title or "", body or "")
        spawn_req = SpawnRequest(
            repo=req.repo,
            issue_number=req.issue_number,
            title=title or f"Issue #{req.issue_number}",
            prompt=prompt
        )
        session = await runner.spawn_agent(spawn_req)

        if session.worktree_path and session.git_branch:
            asyncio.create_task(post_takeover_notice(req.repo, req.issue_number, session.worktree_path, session.git_branch))
        asyncio.create_task(sync_issue_board_status(req.repo, req.issue_number, "in_progress"))

        return {
            "status": "ok",
            "message": f"Agent started for Issue #{req.issue_number}",
            "session_id": session.session_id,
            "worktree": session.worktree_path,
            "branch": session.git_branch
        }
    except Exception as e:
        logger.exception(f"Error starting agent for {req.repo}#{req.issue_number}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pause")
async def pause_issue_agent(req: IssueActionRequest):
    """Pauses the active agent running on the specified issue."""
    sessions = [
        s for s in runner.sessions.values()
        if s.repo == req.repo and s.issue_number == req.issue_number and s.status == AgentStatus.RUNNING
    ]
    if not sessions:
        raise HTTPException(status_code=404, detail="No running agent found for this issue")
    sess = sessions[0]
    await runner.interrupt_agent(sess.session_id)
    return {"status": "ok", "message": f"Agent for Issue #{req.issue_number} paused", "session_id": sess.session_id}


@router.post("/stop")
async def stop_issue_agent(req: IssueActionRequest):
    """Stops the active agent running on the specified issue."""
    sessions = [
        s for s in runner.sessions.values()
        if s.repo == req.repo and s.issue_number == req.issue_number and s.status in [AgentStatus.RUNNING, AgentStatus.PAUSED, AgentStatus.INITIALIZING]
    ]
    if not sessions:
        raise HTTPException(status_code=404, detail="No active agent found for this issue")
    sess = sessions[0]
    await runner.stop_agent(sess.session_id, reason="Stopped via Issue Command Center")
    return {"status": "ok", "message": f"Agent for Issue #{req.issue_number} stopped", "session_id": sess.session_id}


@router.post("/restart")
async def restart_issue_agent(req: IssueActionRequest):
    """Wipes the slate clean for an issue's agent and restarts a fresh agent instance."""
    try:
        existing = [
            s for s in runner.sessions.values()
            if s.repo == req.repo and s.issue_number == req.issue_number
        ]
        for old_sess in existing:
            try:
                await runner.stop_agent(old_sess.session_id, reason="Wiped clean for restart")
                old_sess.is_archived = True
            except Exception as e:
                logger.warning(f"Error stopping old session {old_sess.session_id}: {e}")

        title = req.title
        body = req.body
        if not title:
            data = await get_all_projects_data()
            for p in data.get("projects", []):
                for item in p.get("items", []):
                    if item.get("repo") == req.repo and item.get("number") == req.issue_number:
                        title = item.get("title")
                        body = item.get("body")
                        break

        prompt = _format_issue_prompt(req.repo, req.issue_number, title or "", body or "")
        spawn_req = SpawnRequest(
            repo=req.repo,
            issue_number=req.issue_number,
            title=title or f"Issue #{req.issue_number}",
            prompt=prompt
        )
        session = await runner.spawn_agent(spawn_req)

        if session.worktree_path and session.git_branch:
            asyncio.create_task(post_takeover_notice(req.repo, req.issue_number, session.worktree_path, session.git_branch))
        asyncio.create_task(sync_issue_board_status(req.repo, req.issue_number, "in_progress"))

        return {
            "status": "ok",
            "message": f"Agent restarted fresh for Issue #{req.issue_number}",
            "session_id": session.session_id,
            "worktree": session.worktree_path,
            "branch": session.git_branch
        }
    except Exception as e:
        logger.exception(f"Error restarting agent for {req.repo}#{req.issue_number}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
