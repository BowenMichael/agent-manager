import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
import httpx

from agent_manager.config import GITHUB_PERSONAL_ACCESS_TOKEN
from agent_manager.utils.workspace import find_local_workspace
from agent_manager.runner import AgentRunnerManager
from agent_manager.services.projects_service import PROJECTS_CONFIG, fetch_board_items

logger = logging.getLogger("agent_manager.services.projects_aggregator")


def _enrich_session(session) -> Optional[Dict[str, Any]]:
    if not session:
        return None
    return {
        "session_id": session.session_id,
        "status": session.status.value if hasattr(session.status, "value") else str(session.status),
        "model": session.model,
        "turn_count": session.turn_count,
        "quota_percent": session.quota_percent,
        "is_stalled": session.is_stalled,
        "branch": getattr(session, "git_branch", None),
        "worktree": getattr(session, "worktree_path", None),
        "pr_url": getattr(session, "pr_url", None),
        "pr_number": getattr(session, "pr_number", None),
        "updated_at": getattr(session, "updated_at", None)
    }


async def get_all_projects_data() -> Dict[str, Any]:
    """Aggregates all project details, local workspaces, boards, and active sessions."""
    board_items = await fetch_board_items()
    board_item_map = {f"{item['repo']}#{item['number']}": item for item in board_items}

    runner = AgentRunnerManager()
    sessions = runner.list_sessions(include_archived=True)
    session_map = {}
    for s in sessions:
        key = f"{s.repo}#{s.issue_number}"
        # Keep the most recently updated or active session for an issue
        if key not in session_map or s.status.value == "RUNNING":
            session_map[key] = s

    enriched_projects = []
    all_items = list(board_items)

    for p in PROJECTS_CONFIG:
        repo = p["repo"]
        ws = find_local_workspace(repo)
        local_path = str(ws) if ws else None
        exists_locally = ws is not None

        # Collect items belonging to this project
        project_items = [item for item in all_items if item["repo"] == repo]

        # Attach session and worktree info to each item
        for item in project_items:
            key = f"{item['repo']}#{item['number']}"
            sess = session_map.get(key)
            item["active_session"] = _enrich_session(sess)

            # Check if local worktree exists
            if ws:
                wt_dir = ws / ".worktrees" / f"issue-{item['number']}"
                item["has_local_worktree"] = wt_dir.exists()
                item["worktree_path"] = str(wt_dir) if wt_dir.exists() else None
            else:
                item["has_local_worktree"] = False
                item["worktree_path"] = None

        # Calculate counts
        status_counts = {
            "ready": len([i for i in project_items if "Ready" in i["status"]]),
            "in_progress": len([i for i in project_items if "Progress" in i["status"]]),
            "in_review": len([i for i in project_items if "Review" in i["status"]]),
            "done": len([i for i in project_items if "Done" in i["status"]]),
            "backlog": len([i for i in project_items if "Backlog" in i["status"]]),
            "total": len(project_items)
        }

        active_agents_count = len([
            i for i in project_items
            if i.get("active_session") and i["active_session"]["status"] == "RUNNING"
        ])

        enriched_projects.append({
            **p,
            "local_path": local_path,
            "exists_locally": exists_locally,
            "items": project_items,
            "counts": status_counts,
            "active_agents_count": active_agents_count,
            "github_url": f"https://github.com/{repo}"
        })

    # Global summary stats
    global_counts = {
        "total_projects": len(PROJECTS_CONFIG),
        "total_items": len(all_items),
        "ready": len([i for i in all_items if "Ready" in i["status"]]),
        "in_progress": len([i for i in all_items if "Progress" in i["status"]]),
        "in_review": len([i for i in all_items if "Review" in i["status"]]),
        "done": len([i for i in all_items if "Done" in i["status"]]),
        "active_agents": sum(p["active_agents_count"] for p in enriched_projects)
    }

    return {
        "projects": enriched_projects,
        "global_counts": global_counts,
        "master_board_url": "https://github.com/users/BowenMichael/projects/3"
    }
