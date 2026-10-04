from fastapi import APIRouter, HTTPException
from agent_manager.models import SimulateWebhookRequest, SpawnRequest
from agent_manager.runner import AgentRunnerManager
from agent_manager.poller import LocalGitWatcher
from agent_manager.webhooks import process_github_event
import agent_manager.config as config

router = APIRouter(prefix="/api", tags=["github"])
runner = AgentRunnerManager()
watcher = LocalGitWatcher()


@router.post("/board/sync")
async def sync_board():
    try:
        for b in config.PROJECT_BOARD_IDS:
            await watcher._check_project_board(b)
        return {"status": "ok", "message": "Project board synced successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhooks/simulate")
async def simulate_webhook(req: SimulateWebhookRequest):
    """Simulates a GitHub Webhook event payload for local testing."""
    if req.event_type == "issues":
        prompt = (
            f"You have been assigned to GitHub Issue #{req.issue_number} in {req.repo}.\n\n"
            f"**Title**: {req.issue_title}\n\n"
            f"**Requirements / Description**:\n{req.issue_body}\n\n"
            f"**Operational Guidelines**:\n"
            f"- Work inside the designated branch and isolated worktree.\n"
            f"- Inspect existing code patterns before modifying.\n"
            f"- Follow AGENTS.md rules and keep documentation updated.\n"
            f"- MANDATORY CHANGELOG RULE: Update CHANGELOG.md with your changes before opening a PR or moving to review. Initialize CHANGELOG.md if missing.\n"
            f"- When done, commit changes, open a pull request, and summarize your work."
        )
        spawn_req = SpawnRequest(
            repo=req.repo,
            issue_number=req.issue_number,
            title=req.issue_title,
            prompt=prompt
        )
        session = await runner.spawn_agent(spawn_req)
        return {"status": "ok", "simulated": True, "session": session}

    elif req.event_type == "issue_comment":
        mock_payload = {
            "action": req.action or "created",
            "issue": {
                "number": req.issue_number,
                "title": req.issue_title,
                "body": req.issue_body,
            },
            "comment": {
                "id": req.comment_id or 12345678,
                "body": req.comment_body or "Simulated feedback comment on issue.",
                "user": {"login": req.commenter or "reviewer"}
            },
            "repository": {
                "full_name": req.repo
            }
        }
        result = await process_github_event("issue_comment", mock_payload)
        return {"status": "ok", "simulated": True, "result": result}

    raise HTTPException(status_code=400, detail=f"Unsupported simulation event type: {req.event_type}")
