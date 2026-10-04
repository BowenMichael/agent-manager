import logging
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
import httpx

from agent_manager.config import GITHUB_PERSONAL_ACCESS_TOKEN, PROJECT_BOARD_IDS
from agent_manager.services.projects_aggregator import get_all_projects_data
from agent_manager.poller import LocalGitWatcher

logger = logging.getLogger("agent_manager.api.routes.projects")
router = APIRouter(prefix="/api/projects", tags=["projects"])
watcher = LocalGitWatcher()


class CreateIssueRequest(BaseModel):
    repo: str = Field(..., description="Target repository name e.g. BowenMichael/fit-elo")
    title: str = Field(..., description="Issue title")
    body: Optional[str] = Field("", description="Issue description / requirements")
    status: Optional[str] = Field("📋 Ready for Agent", description="Initial board status")


@router.get("")
async def list_projects():
    """Returns aggregated projects, their issue tables, local workspaces, and active agents."""
    try:
        data = await get_all_projects_data()
        return data
    except Exception as e:
        logger.error(f"Error fetching projects data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def sync_projects():
    """Forces synchronization across all project boards and local workspaces."""
    try:
        for bid in PROJECT_BOARD_IDS:
            await watcher._check_project_board(bid)
        data = await get_all_projects_data()
        return {"status": "ok", "message": "Projects synced successfully", "data": data}
    except Exception as e:
        logger.error(f"Error syncing project boards: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/issues")
async def create_issue(req: CreateIssueRequest):
    """Creates a new issue in the designated project repository and adds it to the project board."""
    if not GITHUB_PERSONAL_ACCESS_TOKEN:
        raise HTTPException(status_code=400, detail="GITHUB_PERSONAL_ACCESS_TOKEN not configured")

    headers = {
        "Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AgentManagerLocal/1.0"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.github.com/repos/{req.repo}/issues",
                json={"title": req.title, "body": req.body or ""},
                headers=headers
            )
            if resp.status_code not in (200, 201):
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"GitHub API Error: {resp.text}"
                )

            issue_data = resp.json()
            num = issue_data.get("number")
            node_id = issue_data.get("node_id")

            # Link issue directly to Project #3 board and set initial status
            if node_id:
                try:
                    add_mutation = """
                    mutation($projectId: ID!, $contentId: ID!) {
                      addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
                        item { id }
                      }
                    }
                    """
                    add_resp = await client.post(
                        "https://api.github.com/graphql",
                        json={"query": add_mutation, "variables": {"projectId": "PVT_kwHOAgkA3s4BlnSi", "contentId": node_id}},
                        headers={"Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}", "Content-Type": "application/json"}
                    )
                    res_json = add_resp.json()
                    item_id = (res_json.get("data", {}).get("addProjectV2ItemById", {}).get("item", {}) or {}).get("id")
                    if item_id:
                        from agent_manager.poller.github_client import GitHubBoardClient
                        board_client = GitHubBoardClient()
                        target_key = "ready"
                        s_lower = str(req.status or "").lower()
                        if "backlog" in s_lower:
                            target_key = "backlog"
                        elif "progress" in s_lower:
                            target_key = "in_progress"
                        await board_client.update_item_status(item_id, target_key, "PVT_kwHOAgkA3s4BlnSi")
                except Exception as ex:
                    logger.warning(f"Could not automatically attach issue to project board: {ex}")

            # Trigger a sync so the watcher registers the new issue
            for bid in PROJECT_BOARD_IDS:
                await watcher._check_project_board(bid)

            return {
                "status": "ok",
                "repo": req.repo,
                "number": num,
                "title": issue_data.get("title"),
                "url": issue_data.get("html_url")
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create issue in {req.repo}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
