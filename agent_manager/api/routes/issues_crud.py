import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from agent_manager.services.projects_aggregator import get_all_projects_data
from agent_manager.poller import LocalGitWatcher
from agent_manager.config import PROJECT_BOARD_IDS

logger = logging.getLogger("agent_manager.api.routes.issues_crud")
router = APIRouter()
watcher = LocalGitWatcher()


class IssueActionRequest(BaseModel):
    repo: str = Field(..., description="Repository full name, e.g. BowenMichael/fit-elo")
    issue_number: int = Field(..., description="GitHub Issue Number")
    title: Optional[str] = Field(None, description="Issue title if known")
    body: Optional[str] = Field(None, description="Issue description / requirements if known")


@router.get("/")
async def get_all_issues():
    """Returns a unified flat list of all issues across tracked repositories with status and active agent details."""
    try:
        data = await get_all_projects_data()
        all_issues = []
        for project in data.get("projects", []):
            for item in project.get("items", []):
                all_issues.append({
                    **item,
                    "project_id": project.get("id"),
                    "project_name": project.get("name"),
                    "project_icon": project.get("icon"),
                })
        return {
            "issues": all_issues,
            "counts": data.get("global_counts", {}),
            "projects": [
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "repo": p.get("repo"),
                    "icon": p.get("icon"),
                    "counts": p.get("counts", {}),
                    "active_agents_count": p.get("active_agents_count", 0),
                }
                for p in data.get("projects", [])
            ]
        }
    except Exception as e:
        logger.exception(f"Error fetching issues: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def sync_issues():
    """Forces synchronization across all GitHub project boards."""
    try:
        for bid in PROJECT_BOARD_IDS:
            await watcher._check_project_board(bid)
        return {"status": "ok", "message": "All project boards synchronized successfully"}
    except Exception as e:
        logger.exception(f"Error syncing boards: {e}")
        raise HTTPException(status_code=500, detail=str(e))
