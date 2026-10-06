"""
Automated Multi-Agent Peer Review & Security Audit Gateway.
Adversarial PR Peer Reviewer persona auditing PR diffs for security vulnerabilities,
syntax flaws, test coverage, and Section 5 Anti-Monolith limits before In Review.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

import httpx
from agent_manager.models import AgentSessionInfo, ConversationMessage, MessageRole
from agent_manager.services.security_audit_service import audit_worktree_diff

logger = logging.getLogger("agent_manager.runners.reviewer")


def format_review_markdown(audit_res: Dict[str, Any], branch: Optional[str] = None) -> str:
    """Synthesizes structured GitHub PR review markdown with findings breakdown."""
    passed = audit_res.get("passed", False)
    status_icon = "✅ **APPROVE**" if passed else "🚫 **REQUEST CHANGES**"
    flaws = audit_res.get("critical_flaws", [])
    warnings = audit_res.get("warnings", [])

    lines = [
        f"### 🛡️ Automated Swarm Peer Review: {status_icon}",
        f"- **Branch**: `{branch or 'HEAD'}`",
        f"- **Files Audited**: {len(audit_res.get('changed_files', []))}",
        f"- **Critical Flaws**: {len(flaws)}",
        f"- **Warnings**: {len(warnings)}",
        ""
    ]

    if flaws:
        lines.append("#### ❌ Critical Blockers (Must Fix Prior to Merge):")
        for f in flaws:
            lines.append(f"- 🔴 {f}")
        lines.append("")

    if warnings:
        lines.append("#### ⚠️ Code Quality & Test Coverage Advisory:")
        for w in warnings:
            lines.append(f"- 🟡 {w}")
        lines.append("")

    if passed:
        lines.append("🎉 **All static security, AST syntax, and Anti-Monolith gates passed cleanly.**")
    lines.append("\n*Automated review posted by Agent Manager Peer Reviewer Gateway.*")
    return "\n".join(lines)


async def submit_github_pr_review(repo: str, pr_number: int, event: str, body: str) -> bool:
    """Submits a formal review (APPROVE or REQUEST_CHANGES) via GitHub REST API or gh CLI."""
    token = os.getenv("GITHUB_TOKEN", "")
    if token:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews",
                    headers={
                        "Authorization": f"token {token}",
                        "Accept": "application/vnd.github.v3+json"
                    },
                    json={"event": event, "body": body},
                    timeout=15.0
                )
                if res.status_code in (200, 201):
                    logger.info(f"Successfully posted PR review to {repo}#{pr_number}")
                    return True
        except Exception as e:
            logger.warning(f"Direct API call for PR review failed: {e}")

    try:
        gh_event = "--approve" if event == "APPROVE" else "--request-changes"
        subprocess.run(
            ["gh", "pr", "review", str(pr_number), "--repo", repo, gh_event, "-b", body],
            capture_output=True, text=True, check=True
        )
        logger.info(f"Successfully posted PR review via gh CLI to {repo}#{pr_number}")
        return True
    except Exception as e:
        logger.warning(f"Could not submit PR review via gh CLI: {e}")
        return False


async def run_peer_reviewer_gateway(
    session: AgentSessionInfo,
    worktree_path: Path,
    branch: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes peer review gateway: audits diff, synthesizes PR feedback,
    and determines whether to allow transition to IN_REVIEW.
    """
    audit_res = audit_worktree_diff(worktree_path)
    passed = audit_res["passed"]
    event = "APPROVE" if passed else "REQUEST_CHANGES"
    review_body = format_review_markdown(audit_res, branch)

    session.messages.append(
        ConversationMessage(
            id=f"peer-review-{len(session.messages)}",
            role=MessageRole.SYSTEM,
            content=review_body
        )
    )

    if session.repo and session.pr_number:
        await submit_github_pr_review(session.repo, session.pr_number, event, review_body)

    if not passed:
        logger.warning(
            f"[Peer Reviewer] Session {session.session_id} blocked by peer review: "
            f"{len(audit_res['critical_flaws'])} critical flaw(s)."
        )

    return {
        "passed": passed,
        "event": event,
        "critical_flaws": audit_res["critical_flaws"],
        "warnings": audit_res["warnings"],
        "summary": review_body
    }
