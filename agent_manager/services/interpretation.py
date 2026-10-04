"""
Service for generating pre-execution Agent Interpretation on sparse or title-only issues
before transitioning them to '⚡ In Progress' on the Project Board.
"""
import logging
import asyncio
from typing import Optional, Any
from agent_manager import config
from agent_manager.models import MessageRole, SpawnRequest, AgentSessionInfo
from agent_manager.github import post_issue_comment
from agent_manager.services.issue_evaluator import is_sparse_issue
from agent_manager.formatters.comments import (
    format_agent_comment,
    BADGE_AGENT_INTERPRETATION,
)

logger = logging.getLogger("agent_manager.services.interpretation")


def build_interpretation_prompt(title: str, body: Optional[str], issue_num: int) -> str:
    """Constructs prompt for the requirements elaboration CLI turn."""
    raw_desc = body.strip() if body else "No description provided (title only)."
    return (
        f"You are a principal software requirements analyst. "
        f"The following GitHub Issue #{issue_num} was created with minimal or title-only details:\n\n"
        f"**Title**: {title}\n"
        f"**Original Description**:\n{raw_desc}\n\n"
        f"Please formulate a comprehensive, structured technical elaboration for this task:\n"
        f"1. **Agent Interpretation & Inferred Scope**: Explain what this task entails and the intended user/system outcome.\n"
        f"2. **Detailed Requirements Breakdown**: Expand into concrete functional requirements.\n"
        f"3. **Proposed Acceptance Criteria**: Provide clear checkbox criteria (`- [ ] ...`) for verification.\n"
        f"4. **Technical Boundaries & Constraints**: Note any relevant modules, conventions, or constraints.\n\n"
        f"IMPORTANT: You must explicitly designate this elaboration as an **Agent Interpretation** "
        f"so human maintainers understand this represents inferred requirements."
    )


async def generate_and_post_interpretation(
    runner: Any,
    session: AgentSessionInfo,
    repo: str,
    issue_num: int,
    title: str,
    body: Optional[str]
) -> Optional[str]:
    """
    Runs a CLI turn to elaborate the sparse issue, formats it with standard badges and footers,
    and posts the interpretation comment to GitHub.
    """
    logger.info("Generating Agent Interpretation for sparse Issue #%s (%s)", issue_num, repo)
    session.current_activity = "Elaborating issue requirements (Agent Interpretation)..."
    runner._save()
    await runner.broadcast("session_updated", session.model_dump())

    interp_model = getattr(config, "PIPELINE_SUMMARY_MODEL", getattr(config, "DEFAULT_MODEL", "gemini-3.8-flash"))
    interp_effort = getattr(config, "PIPELINE_SUMMARY_EFFORT", getattr(config, "DEFAULT_EFFORT", "low"))

    prompt = build_interpretation_prompt(title, body, issue_num)
    cwd_dir = session.worktree_path or str(config.WORKSPACE_BASE)

    try:
        raw_interpretation = await runner._run_cli_turn(
            session_id=session.session_id,
            prompt=prompt,
            cwd_dir=cwd_dir,
            model=interp_model,
            effort=interp_effort
        )
    except Exception as e:
        logger.error("Failed to generate interpretation via CLI turn for #%s: %e", issue_num, e)
        return None

    if not raw_interpretation or not raw_interpretation.strip():
        logger.warning("Empty interpretation generated for Issue #%s", issue_num)
        return None

    interpretation_text = raw_interpretation.strip()

    # Format into standard agent comment with badge and footer
    formatted_comment = format_agent_comment(
        body=interpretation_text,
        header=BADGE_AGENT_INTERPRETATION,
        session_id=session.session_id,
        worktree_path=session.worktree_path,
        git_branch=session.git_branch
    )

    # Post directly to the GitHub issue
    await post_issue_comment(repo, issue_num, formatted_comment)
    logger.info("Posted Agent Interpretation comment to Issue #%s on GitHub", issue_num)

    await runner._append_message(
        session.session_id,
        MessageRole.AGENT,
        f"📋 **Agent Interpretation Posted to Issue #{issue_num}**:\n\n{interpretation_text}"
    )
    runner._save()
    await runner.broadcast("session_updated", session.model_dump())

    return interpretation_text


async def run_interpretation_and_start(
    watcher: Any,
    item_id: str,
    issue_key: str,
    spawn_req: SpawnRequest,
    session: AgentSessionInfo,
    raw_body: Optional[str]
):
    """
    Inspects issue content; if sparse, elaborates and posts interpretation before
    transitioning the Project Board card to '⚡ In Progress' and launching the agent loop.
    """
    repo = spawn_req.repo or session.repo
    issue_num = spawn_req.issue_number or session.issue_number
    title = spawn_req.title or session.title
    active_prompt = spawn_req.prompt

    if is_sparse_issue(raw_body):
        logger.info(
            "Issue #%s identified as sparse/title-only. Starting pre-execution interpretation phase.",
            issue_num
        )
        interpretation = await generate_and_post_interpretation(
            runner=watcher.runner,
            session=session,
            repo=repo,
            issue_num=issue_num,
            title=title,
            body=raw_body
        )
        if interpretation:
            active_prompt = (
                f"{active_prompt}\n\n"
                f"### Elaborated Agent Interpretation & Context:\n"
                f"{interpretation}\n\n"
                f"Please follow the elaborated requirements and acceptance criteria outlined above."
            )

    # Step: Transition Project Board status to '⚡ In Progress'
    await watcher.update_item_status(item_id, "in_progress")
    logger.info("Updated Issue #%s Project Board status to '⚡ In Progress'", issue_num)

    # Step: Launch main agent execution loop in worktree
    loop_task = asyncio.create_task(
        watcher.runner._run_agent_loop(
            session_id=session.session_id,
            initial_prompt=active_prompt,
            worktree_path=session.worktree_path,
            is_continuation=False
        )
    )
    watcher.runner._tasks[session.session_id] = loop_task
