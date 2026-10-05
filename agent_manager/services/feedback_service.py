"""
Universal Feedback Flywheel Ingestion Service.
Synthesizes telemetry, error logs, and user feedback into structured GitHub issues
and automatically places them into Project Board column 'Ready for Agent'.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import logging
import json
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
import httpx

from agent_manager.config import GITHUB_PERSONAL_ACCESS_TOKEN, DEFAULT_REPO
from agent_manager.poller.github_client import GitHubBoardClient

logger = logging.getLogger("agent_manager.services.feedback")

APP_REPO_MAP = {
    "fitelo": "BowenMichael/fit-elo",
    "fit-elo": "BowenMichael/fit-elo",
    "better_buisness_deal": "BowenMichael/better_buisness_deal",
    "better business deal": "BowenMichael/better_buisness_deal",
    "f1-frontend": "BowenMichael/f1-frontend",
    "f1": "BowenMichael/f1-frontend",
    "leanfolio": "BowenMichael/leanfolio",
    "agent-manager": "BowenMichael/agent-manager",
    "agent manager": "BowenMichael/agent-manager",
}


class FeedbackSubmissionRequest(BaseModel):
    app_name: str = Field(..., description="Name of the calling application")
    target_repo: Optional[str] = Field(None, description="Explicit target GitHub repo")
    feedback_type: str = Field("bug", description="bug | feature | ux_polish")
    title: str = Field(..., description="Short summary of feedback or issue")
    description: str = Field(..., description="User provided details or steps to reproduce")
    route: Optional[str] = Field(None, description="Application route/URL where feedback was submitted")
    user_agent: Optional[str] = Field(None, description="Client browser or mobile user agent")
    viewport: Optional[Dict[str, int]] = Field(None, description="Screen width/height dimensions")
    console_logs: Optional[List[Dict[str, Any]]] = Field(None, description="Recent console error logs")
    screenshot_base64: Optional[str] = Field(None, description="Optional base64 encoded screenshot")
    user_email: Optional[str] = Field(None, description="Submitter email for follow-up")
    auto_assign: bool = Field(True, description="Whether to auto-advance onto Project Board")


def resolve_target_repo(app_name: str, target_repo: Optional[str] = None) -> str:
    """Resolves repo full name from explicit target or app name mapping."""
    if target_repo:
        return target_repo
    key = app_name.strip().lower()
    return APP_REPO_MAP.get(key, DEFAULT_REPO)


def format_feedback_body(req: FeedbackSubmissionRequest, repo: str) -> str:
    """Formats rich diagnostic GitHub Issue markdown body."""
    logs_section = ""
    if req.console_logs:
        log_lines = "\n".join(
            f"[{l.get('level', 'log').upper()}] {l.get('message', '')}"
            for l in req.console_logs[-10:]
        )
        logs_section = f"\n```\n{log_lines}\n```"

    viewport_str = f"{req.viewport.get('width', '?')}x{req.viewport.get('height', '?')}" if req.viewport else "N/A"

    return (
        f"### 🎯 Overview & User Description\n"
        f"**Type**: `{req.feedback_type.upper()}` | **Origin**: `{req.app_name}`\n\n"
        f"{req.description}\n\n"
        f"### 📋 Acceptance Criteria\n"
        f"- [ ] Investigate and resolve `{req.title}` in `{repo}`.\n"
        f"- [ ] Verify fix locally and on deployed route `{req.route or '/'}`.\n"
        f"- [ ] Add matching unit or integration tests.\n"
        f"- [ ] Update `CHANGELOG.md` under `[Unreleased]`.\n\n"
        f"<details>\n"
        f"<summary>🔍 Client Diagnostics & Telemetry</summary>\n\n"
        f"- **Route**: `{req.route or 'N/A'}`\n"
        f"- **Viewport**: `{viewport_str}`\n"
        f"- **User Agent**: `{req.user_agent or 'N/A'}`\n"
        f"- **Submitter**: `{req.user_email or 'Anonymous'}`\n"
        f"{logs_section}\n"
        f"</details>\n\n"
        f"---\n"
        f"*Submitted via Universal Autonomous Feedback Flywheel*"
    )


async def create_github_issue(repo: str, title: str, body: str) -> Optional[Dict[str, Any]]:
    """Creates a GitHub issue using REST API with authorization token."""
    if not GITHUB_PERSONAL_ACCESS_TOKEN:
        logger.warning("GITHUB_PERSONAL_ACCESS_TOKEN not set; skipping GitHub issue creation.")
        return None

    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AgentManagerFeedbackFlywheel/1.0"
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json={"title": title, "body": body}, headers=headers)
            if resp.status_code in [200, 201]:
                return resp.json()
            logger.error(f"Failed to create GitHub issue in {repo}: HTTP {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        logger.exception(f"Exception creating GitHub issue in {repo}: {e}")
        return None


async def ingest_feedback(req: FeedbackSubmissionRequest) -> Dict[str, Any]:
    """Processes incoming feedback, creates GitHub issue, and syncs to Ready for Agent."""
    repo = resolve_target_repo(req.app_name, req.target_repo)
    full_title = f"[{req.feedback_type.upper()}]: {req.title}"
    body = format_feedback_body(req, repo)

    issue_data = await create_github_issue(repo, full_title, body)
    if not issue_data:
        return {
            "success": False,
            "error": "Failed to create GitHub issue. Verify token and repo permissions."
        }

    issue_number = issue_data.get("number")
    board_status = "Ready for Agent"

    if req.auto_assign:
        try:
            from agent_manager.poller import LocalGitWatcher
            watcher = LocalGitWatcher()
            await watcher.update_issue_status(repo, issue_number, "ready")
        except Exception as e:
            logger.warning(f"Could not immediately update Project Board status for {repo}#{issue_number}: {e}")

    return {
        "success": True,
        "repo": repo,
        "issue_number": issue_number,
        "title": full_title,
        "url": issue_data.get("html_url"),
        "status": board_status,
        "auto_assigned": req.auto_assign
    }
