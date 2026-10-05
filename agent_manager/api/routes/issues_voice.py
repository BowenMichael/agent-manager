import logging
import asyncio
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
import httpx

from agent_manager.runner import AgentRunnerManager
from agent_manager.models import SpawnRequest
from agent_manager.poller import LocalGitWatcher
from agent_manager.runners.supervisor import post_takeover_notice, sync_issue_board_status
from agent_manager.config import PROJECT_BOARD_IDS, GITHUB_PERSONAL_ACCESS_TOKEN
from agent_manager.services.voice_issue_service import structure_spoken_issue
from agent_manager.api.routes.issues_actions import _format_issue_prompt

logger = logging.getLogger("agent_manager.api.routes.issues_voice")
router = APIRouter()
runner = AgentRunnerManager()
watcher = LocalGitWatcher()


class VoiceIssueRequest(BaseModel):
    transcript: str = Field(..., description="Spoken voice transcript")
    target_repo: Optional[str] = Field(None, description="Optional target repo override")
    auto_assign: bool = Field(True, description="Whether to automatically launch agent on created issue")


async def _attach_to_project_board(client: httpx.AsyncClient, node_id: str, auto_assign: bool) -> None:
    mutation = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
        item { id }
      }
    }
    """
    try:
        resp = await client.post(
            "https://api.github.com/graphql",
            json={"query": mutation, "variables": {"projectId": "PVT_kwHOAgkA3s4BlnSi", "contentId": node_id}},
            headers={"Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}", "Content-Type": "application/json"}
        )
        res_json = resp.json()
        item_id = (res_json.get("data", {}).get("addProjectV2ItemById", {}).get("item", {}) or {}).get("id")
        if item_id:
            from agent_manager.poller.github_client import GitHubBoardClient
            board_client = GitHubBoardClient()
            target_key = "in_progress" if auto_assign else "ready"
            await board_client.update_item_status(item_id, target_key, "PVT_kwHOAgkA3s4BlnSi")
    except Exception as ex:
        logger.warning(f"Could not attach voice issue to project board: {ex}")


@router.post("/voice-create")
async def voice_create_issue(req: VoiceIssueRequest):
    """Processes spoken voice memo, details it into a structured GitHub issue, attaches it to the board, and optionally assigns an agent."""
    if not req.transcript.strip():
        raise HTTPException(status_code=400, detail="Voice transcript cannot be empty")
        
    structured = await structure_spoken_issue(req.transcript, req.target_repo)
    repo = structured["repo"]
    title = structured["title"]
    body = structured["body"]

    if not GITHUB_PERSONAL_ACCESS_TOKEN:
        raise HTTPException(status_code=400, detail="GITHUB_PERSONAL_ACCESS_TOKEN not configured")

    headers = {
        "Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AgentManagerVoiceListener/1.0"
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"https://api.github.com/repos/{repo}/issues",
                json={"title": title, "body": body},
                headers=headers
            )
            if resp.status_code not in (200, 201):
                raise HTTPException(status_code=resp.status_code, detail=f"GitHub API Error: {resp.text}")
            issue_data = resp.json()
            num = issue_data.get("number")
            node_id = issue_data.get("node_id")

            if node_id:
                await _attach_to_project_board(client, node_id, req.auto_assign)

        for bid in PROJECT_BOARD_IDS:
            await watcher._check_project_board(bid)

        session_id, worktree, branch = None, None, None
        if req.auto_assign:
            prompt = _format_issue_prompt(repo, num, title, body)
            spawn_req = SpawnRequest(repo=repo, issue_number=num, title=title, prompt=prompt)
            session = await runner.spawn_agent(spawn_req)
            session_id = session.session_id
            worktree = session.worktree_path
            branch = session.git_branch

            if session.worktree_path and session.git_branch:
                asyncio.create_task(post_takeover_notice(repo, num, session.worktree_path, session.git_branch))
            asyncio.create_task(sync_issue_board_status(repo, num, "in_progress"))

        return {
            "status": "ok",
            "repo": repo,
            "number": num,
            "title": title,
            "url": issue_data.get("html_url"),
            "auto_assigned": req.auto_assign,
            "session_id": session_id,
            "worktree": worktree,
            "branch": branch
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating voice issue: {e}")
        raise HTTPException(status_code=500, detail=str(e))
