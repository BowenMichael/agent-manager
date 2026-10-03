import hmac
import hashlib
import json
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Header, HTTPException, status

from agent_manager.config import GITHUB_WEBHOOK_SECRET, DEFAULT_REPO
from agent_manager.models import SpawnRequest
from agent_manager.runner import AgentRunnerManager

logger = logging.getLogger("agent_manager.webhooks")
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

def verify_signature(payload: bytes, signature_header: Optional[str]) -> bool:
    if not GITHUB_WEBHOOK_SECRET:
        return True
    if not signature_header:
        return False
    try:
        hash_type, signature = signature_header.split("=")
        if hash_type != "sha256":
            return False
        mac = hmac.new(GITHUB_WEBHOOK_SECRET.encode(), payload, hashlib.sha256)
        return hmac.compare_digest(mac.hexdigest(), signature)
    except Exception:
        return False

@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: Optional[str] = Header(None),
    x_hub_signature_256: Optional[str] = Header(None)
):
    body_bytes = await request.body()
    if not verify_signature(body_bytes, x_hub_signature_256):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid GitHub webhook HMAC signature"
        )

    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event = x_github_event or "unknown"
    logger.info(f"Received GitHub webhook event: {event}")
    runner = AgentRunnerManager()

    # 1. Handling Issues Events
    if event == "issues":
        action = payload.get("action")
        issue = payload.get("issue", {})
        repo = payload.get("repository", {}).get("full_name", DEFAULT_REPO)
        issue_number = issue.get("number")
        title = issue.get("title", "")
        body = issue.get("body", "")
        labels = [l.get("name", "") for l in issue.get("labels", [])]

        ready_triggers = ["agent:ready", "ready-for-agent", "ready"]
        is_ready = any(t in labels for t in ready_triggers)

        if action in ["labeled", "opened", "reopened"] and is_ready:
            prompt = (
                f"You have been assigned to GitHub Issue #{issue_number} in {repo}.\n\n"
                f"**Title**: {title}\n\n"
                f"**Requirements / Description**:\n{body}\n\n"
                f"**Operational Guidelines**:\n"
                f"- Work inside the designated branch and isolated worktree.\n"
                f"- Inspect existing code patterns before modifying.\n"
                f"- Follow AGENTS.md rules and keep documentation updated.\n"
                f"- When done, commit changes, open a pull request, and summarize your work."
            )
            req = SpawnRequest(
                repo=repo,
                issue_number=issue_number,
                title=title,
                prompt=prompt
            )
            session = await runner.spawn_agent(req)
            return {"status": "ok", "action": "agent_spawned", "session_id": session.session_id}

    # 2. Handling Project V2 Item Status Updates (Ready for Agent)
    elif event == "projects_v2_item":
        action = payload.get("action")
        item = payload.get("projects_v2_item", {})
        content_type = item.get("content_type")

        # Check if item is an Issue
        if content_type == "Issue":
            changes = payload.get("changes", {})
            field_value = changes.get("field_value", {})
            field_name = field_value.get("field_name")
            to_value = field_value.get("to") or {}
            to_name = to_value.get("name", "")

            if "Ready for Agent" in to_name or "ready" in to_name.lower():
                # Extract issue details or fallback to default repo
                issue_number = item.get("content_node_id") # May require query or metadata
                prompt = (
                    f"An issue on the Project Board was moved to '📋 Ready for Agent'.\n"
                    f"Please review the Project Board, inspect the card details, and execute the task following AGENTS.md."
                )
                req = SpawnRequest(
                    repo=DEFAULT_REPO,
                    title="Board Card: Ready for Agent",
                    prompt=prompt
                )
                session = await runner.spawn_agent(req)
                return {"status": "ok", "action": "board_agent_spawned", "session_id": session.session_id}

    # 3. Handling Issue Comments (Context Injection)
    elif event == "issue_comment":
        action = payload.get("action")
        if action == "created":
            issue = payload.get("issue", {})
            comment = payload.get("comment", {})
            issue_number = issue.get("number")
            commenter = comment.get("user", {}).get("login", "user")
            body = comment.get("body", "")

            # Look for active session matching this issue number
            for session in runner.list_sessions():
                if session.issue_number == issue_number and session.status in ["RUNNING", "PAUSED"]:
                    context_text = f"Additional context from GitHub user @{commenter}:\n\n{body}"
                    await runner.add_context(session.session_id, context_text)
                    return {"status": "ok", "action": "context_injected", "session_id": session.session_id}

    return {"status": "ignored", "event": event, "action": payload.get("action")}
