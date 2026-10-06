"""
GitHub Project Board and Issue Synchronization Logic.
Handles state transitions, comment injection, and WebSocket sync broadcasting.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import asyncio
import logging
from typing import Dict, Any, List
from agent_manager import config
from agent_manager.models import SpawnRequest, AgentStatus
from agent_manager.formatters.comments import is_agent_comment
from agent_manager.poller.constants import STATUS_NAMES, is_empty_or_template_only
from agent_manager.services.interpretation import run_interpretation_and_start

logger = logging.getLogger("agent_manager.poller.sync")


async def broadcast_board_sync(watcher, issue_num: int, repo: str, status_key: str):
    """Broadcasts board status synchronization events to connected WebSocket clients."""
    try:
        await watcher.runner.broadcast({
            "type": "board_status_sync",
            "data": {
                "issue_number": issue_num,
                "repo": repo,
                "status": status_key
            }
        })
    except Exception as e:
        logger.debug("Failed to broadcast board sync: %s", e)


async def handle_closed_or_done(watcher, item_id: str, issue_num: int, repo: str, issue_state: str, status_name: str, issue_key: str):
    """Processes issues that have moved to Done or closed on GitHub."""
    if issue_state == "CLOSED" and status_name != STATUS_NAMES["done"]:
        await watcher.update_item_status(item_id, "done")
        logger.info("Issue #%s detected as CLOSED on GitHub. Moved card to '✅ Done'.", issue_num)
    for s in watcher.runner.list_sessions():
        if s.issue_number == issue_num and s.repo == repo and s.status != AgentStatus.COMPLETED:
            logger.info("Issue #%s closed/done. Completing session %s", issue_num, s.session_id)
            await watcher.runner.complete_agent(s.session_id, reason="Issue closed/merged on GitHub")
    watcher.active_issues.discard(issue_key)
    await broadcast_board_sync(watcher, issue_num, repo, "done")


async def handle_active_session_comments(watcher, active_session, item_id: str, issue_num: int, repo: str, body: str, comments: List[Dict[str, Any]], status_name: str) -> bool:
    """Injects new user feedback comments as continuation passes into active sessions."""
    seen_ids = {str(x) for x in active_session.seen_comment_ids}
    new_comments = [
        c for c in comments
        if str(c.get("id")) not in seen_ids and not is_agent_comment(c.get("body"))
    ]
    if not new_comments:
        return False

    update_sections = ["### New Comment(s) from User on GitHub:"]
    for nc in new_comments:
        author = nc.get("author", {}).get("login", "User")
        update_sections.append(f"- **@{author}**: {nc.get('body', '').strip()}")
        active_session.seen_comment_ids.append(str(nc.get("id")))

    feedback_text = "\n\n".join(update_sections)
    logger.info("Issue #%s has %d new user comment(s). Injecting context into %s.", issue_num, len(new_comments), active_session.session_id)
    active_session.last_issue_body = body
    watcher.runner._save()

    if status_name != STATUS_NAMES["in_progress"]:
        await watcher.update_item_status(item_id, "in_progress")
        await broadcast_board_sync(watcher, issue_num, repo, "in_progress")

    continuation_prompt = (
        f"A user commented on GitHub Issue #{issue_num} ({repo}):\n\n{feedback_text}\n\n"
        f"**Guidelines**: Address the feedback directly, run tests, and update CHANGELOG.md."
    )
    await watcher.runner.add_context(active_session.session_id, continuation_prompt)
    return True


def _build_takeover_prompt(issue_num: int, repo: str, title: str, body: str) -> str:
    """Constructs standard takeover execution prompt for autonomous agent sessions."""
    prompt_body = body
    if is_empty_or_template_only(body):
        prompt_body = f"{body}\n\n⚠️ Focus strictly on title objective: '{title}'."
    max_turns = getattr(config, 'MAX_TURNS_PER_SESSION', 15)
    guardrails_line = (
        f"- CIRCUIT BREAKER ACTIVE: Max {max_turns} turns per session.\n"
        if getattr(config, 'GUARDRAILS_ENABLED', True) else
        "- SAFETY GUARDRAILS DISABLED.\n"
    )
    return (
        f"You have been assigned to GitHub Issue #{issue_num} in {repo}.\n\n"
        f"**Title**: {title}\n\n**Requirements**:\n{prompt_body}\n\n"
        f"**Guidelines**:\n- Work in .worktrees/issue-{issue_num}.\n"
        f"- Sliced reads only (max 100 lines per view_file).\n"
        f"- Never create files > 250 LOC; functions <= 40 LOC.\n{guardrails_line}"
        f"- MANDATORY CHANGELOG: Update CHANGELOG.md under [Unreleased] referencing Issue #{issue_num}."
    )


async def handle_ready_status(watcher, active_session, item_id: str, issue_num: int, repo: str, title: str, body: str, comments: List[Dict[str, Any]], issue_key: str):
    """Processes items in 'Ready for Agent', spawning new sessions or re-triggering passes."""
    if active_session:
        active_session.last_issue_body = body
        watcher.runner._save()
        await watcher.update_item_status(item_id, "in_progress")
        await broadcast_board_sync(watcher, issue_num, repo, "in_progress")
        prompt = f"Issue #{issue_num} moved back into Ready for Agent. Review work and continue."
        await watcher.runner.add_context(active_session.session_id, prompt)
    else:
        active_sessions = [
            s for s in watcher.runner.list_sessions()
            if s.issue_number == issue_num and s.repo == repo and s.status in [AgentStatus.RUNNING, AgentStatus.INITIALIZING, AgentStatus.PAUSED]
        ]
        if not active_sessions and issue_key not in watcher.active_issues:
            watcher.active_issues.add(issue_key)
            await watcher.update_item_status(item_id, "in_progress")
            await broadcast_board_sync(watcher, issue_num, repo, "in_progress")
            prompt = _build_takeover_prompt(issue_num, repo, title, body)
            spawn_req = SpawnRequest(repo=repo, issue_number=issue_num, title=title, prompt=prompt)
            session = await watcher.runner.spawn_agent(spawn_req, defer_start=True)
            session.seen_comment_ids = [c.get("id") for c in comments if c.get("id")]
            session.last_issue_body = body
            watcher.runner._save()
            asyncio.create_task(run_interpretation_and_start(watcher, item_id, issue_key, spawn_req, session, body))
