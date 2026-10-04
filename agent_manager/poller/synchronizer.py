import asyncio
import logging
from typing import Dict, Any, List
from agent_manager import config
from agent_manager.models import SpawnRequest, AgentStatus
from agent_manager.formatters.comments import is_agent_comment
from agent_manager.poller.constants import STATUS_NAMES, is_empty_or_template_only
from agent_manager.services.interpretation import run_interpretation_and_start

logger = logging.getLogger("agent_manager.poller.sync")


async def handle_closed_or_done(watcher, item_id: str, issue_num: int, repo: str, issue_state: str, status_name: str, issue_key: str):
    if issue_state == "CLOSED" and status_name != STATUS_NAMES["done"]:
        await watcher.update_item_status(item_id, "done")
        logger.info("Issue #%s detected as CLOSED on GitHub. Moved card to '✅ Done' on Project Board.", issue_num)
    for s in watcher.runner.list_sessions():
        if s.issue_number == issue_num and s.repo == repo and s.status != AgentStatus.COMPLETED:
            logger.info("Issue #%s detected as closed/done. Formally completing and archiving session %s", issue_num, s.session_id)
            await watcher.runner.complete_agent(s.session_id, reason="Issue closed/merged on GitHub")
    watcher.active_issues.discard(issue_key)


async def handle_active_session_comments(watcher, active_session, item_id: str, issue_num: int, repo: str, body: str, comments: List[Dict[str, Any]], status_name: str) -> bool:
    seen_ids = {str(x) for x in active_session.seen_comment_ids}
    new_comments = [
        c for c in comments
        if str(c.get("id")) not in seen_ids
        and not is_agent_comment(c.get("body"))
    ]

    if not new_comments:
        return False

    update_sections = ["### New Comment(s) from User on GitHub:"]
    for nc in new_comments:
        author = nc.get("author", {}).get("login", "User")
        update_sections.append(f"- **@{author}**: {nc.get('body', '').strip()}")
        active_session.seen_comment_ids.append(str(nc.get("id")))

    feedback_text = "\n\n".join(update_sections)
    logger.info(
        "Issue #%s has %d new user comment(s). Injecting continuation context into session %s.",
        issue_num, len(new_comments), active_session.session_id
    )
    active_session.last_issue_body = body
    watcher.runner._save()

    if status_name != STATUS_NAMES["in_progress"]:
        await watcher.update_item_status(item_id, "in_progress")
        logger.info("Updated Issue #%s Project Board status to '⚡ In Progress' due to new comment", issue_num)

    continuation_prompt = (
        f"A user commented on GitHub Issue #{issue_num} ({repo}):\n\n"
        f"{feedback_text}\n\n"
        f"**Operational Guidelines**:\n"
        f"- Address the user's question or feedback directly.\n"
        f"- Follow AGENTS.md rules: do not add issue labels, keep status transitions purely on the Project Board.\n"
        f"- If code changes or tests are needed, execute them in your worktree.\n"
        f"- When finished, summarize your findings or post your response."
    )
    await watcher.runner.add_context(active_session.session_id, continuation_prompt)
    return True


async def handle_ready_status(watcher, active_session, item_id: str, issue_num: int, repo: str, title: str, body: str, comments: List[Dict[str, Any]], issue_key: str):
    if active_session:
        body_changed = (
            active_session.last_issue_body is not None and
            body.strip() != active_session.last_issue_body.strip()
        )
        logger.info("Issue #%s was moved back to Ready for Agent. Triggering continuation pass.", issue_num)
        active_session.last_issue_body = body
        watcher.runner._save()

        await watcher.update_item_status(item_id, "in_progress")
        logger.info("Updated Issue #%s Project Board status to '⚡ In Progress'", issue_num)

        prompt_text = f"Issue #{issue_num} has been moved back into Ready for Agent."
        if body_changed:
            prompt_text += f"\n\n### Updated Issue Description:\n{body.strip()}"

        continuation_prompt = (
            f"{prompt_text}\n\n"
            f"Please review the work completed in the worktree, test existing features, and continue working on any remaining requirements."
        )
        await watcher.runner.add_context(active_session.session_id, continuation_prompt)
    else:
        active_sessions = [
            s for s in watcher.runner.list_sessions()
            if s.issue_number == issue_num and s.repo == repo and s.status in [AgentStatus.RUNNING, AgentStatus.INITIALIZING, AgentStatus.PAUSED]
        ]
        if not active_sessions and issue_key not in watcher.active_issues:
            logger.info("Found new issue #%s in Ready for Agent. Preparing agent session and evaluating interpretation...", issue_num)
            watcher.active_issues.add(issue_key)

            prompt_body = body
            if is_empty_or_template_only(body):
                logger.warning(
                    "Issue #%s has empty/placeholder description. Adding guidance note to prevent blind exploratory loops.",
                    issue_num
                )
                prompt_body = (
                    f"{body}\n\n"
                    f"⚠️ **Note on Scope**: The issue description contains template placeholders. "
                    f"Focus strictly on achieving the objective specified in the title: '{title}'. "
                    f"Do not guess non-existent criteria."
                )

            max_turns = getattr(config, 'MAX_TURNS_PER_SESSION', 15)
            guardrails_line = (
                f"- CIRCUIT BREAKER ACTIVE: Duplicate tool calls, excessive consecutive file reads without edits, or exceeding {max_turns} turns will immediately halt execution.\n"
                if getattr(config, 'GUARDRAILS_ENABLED', True) else
                "- SAFETY GUARDRAILS DISABLED: Unrestricted execution mode active per developer settings.\n"
            )

            prompt = (
                f"You have been assigned to GitHub Issue #{issue_num} in {repo}.\n\n"
                f"**Title**: {title}\n\n"
                f"**Requirements / Description**:\n{prompt_body}\n\n"
                f"**Operational Guidelines & Efficiency Rules**:\n"
                f"- Work inside the designated branch and isolated worktree .worktrees/issue-{issue_num}.\n"
                f"- SEARCH FIRST: Always use grep_search to find exact symbol, function, or line locations BEFORE calling view_file.\n"
                f"- SLICE READING ONLY: When calling view_file, ALWAYS supply StartLine and EndLine (max 100 lines at once). NEVER view entire large files over 200 lines.\n"
                f"- NEVER RE-READ: Do NOT call view_file on the same file or line range twice in a row. Rely on context and proceed directly to code edits or tests.\n"
                f"- ANTI-MONOLITH RULE: Never create monolithic files over 250 lines. Decompose logic into modular, single-responsibility files (models, services, utils, components). When modifying large files (>300 lines), extract new functions into separate helper files.\n"
                f"{guardrails_line}"
                f"- Follow AGENTS.md rules and keep documentation updated.\n"
                f"- STANDARDIZED AGENT COMMENT RULE: When posting comments on GitHub issues/PRs, you MUST start with a standardized header badge (e.g., `🤖 **Agent Takeover: Development Started**` or `🤖 **Autonomous Agent**`) and include the disclaimer footer: `\\n\\n---\\n*Posted automatically by Agent Manager | Worktree: .worktrees/issue-{issue_num}*`.\n"
                f"- CRITICAL RULE: Do NOT add, remove, or modify GitHub issue labels/tags. Status transitions are managed purely on the GitHub Project Board columns.\n"
                f"- When done, commit changes, open a pull request, and summarize your work."
            )
            spawn_req = SpawnRequest(
                repo=repo,
                issue_number=issue_num,
                title=title,
                prompt=prompt
            )
            session = await watcher.runner.spawn_agent(spawn_req, defer_start=True)
            session.seen_comment_ids = [c.get("id") for c in comments if c.get("id")]
            session.last_issue_body = body
            watcher.runner._save()

            asyncio.create_task(
                run_interpretation_and_start(
                    watcher=watcher,
                    item_id=item_id,
                    issue_key=issue_key,
                    spawn_req=spawn_req,
                    session=session,
                    raw_body=body
                )
            )
