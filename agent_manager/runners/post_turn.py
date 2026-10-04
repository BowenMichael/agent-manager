import logging
from agent_manager.models import MessageRole, AgentStatus
from agent_manager.formatters.comments import (
    format_agent_comment,
    BADGE_AGENT_UPDATE
)
from agent_manager.github import post_issue_comment
from agent_manager.services.dispatch_trigger import fire_dispatch_hook
import agent_manager.config as config

logger = logging.getLogger("agent_manager.runners.post_turn")


async def handle_turn_completion(manager, session, final_resp: str):
    await manager._append_message(session.session_id, MessageRole.AGENT, final_resp)
    session.status = AgentStatus.IN_REVIEW
    await manager._append_message(
        session.session_id,
        MessageRole.SYSTEM,
        "💬 [Turn Complete] Agent finished this execution turn. The chat remains open and active for follow-up questions, instructions, or reviews until this issue is moved to 'Done' on the Project Board."
    )
    manager._save()
    await manager.broadcast("session_updated", session.model_dump())

    if session.issue_number and session.repo:
        try:
            comment_content = format_agent_comment(
                body=final_resp.strip(),
                header=BADGE_AGENT_UPDATE,
                session_id=session.session_id,
                worktree_path=session.worktree_path,
                git_branch=session.git_branch
            )
            comment_res = await post_issue_comment(session.repo, session.issue_number, comment_content)
            if comment_res and "id" in comment_res:
                session.seen_comment_ids.append(str(comment_res["id"]))
                manager._save()
        except Exception as post_err:
            logger.error(f"Failed to post agent completion comment to GitHub: {post_err}")


async def handle_post_process(manager, session, proc=None, returncode: int = 0):
    rc = returncode if proc is None else getattr(proc, 'returncode', 0)
    if session.status not in [AgentStatus.PAUSED, AgentStatus.STOPPED, AgentStatus.COMPLETED]:
        session.status = AgentStatus.IN_REVIEW if rc == 0 else AgentStatus.FAILED

    if rc == 0 and session.status != AgentStatus.FAILED:
        await manager.compact_session(session.session_id)

        if getattr(config, "AUTO_MERGE_ENABLED", False) and session.repo and session.git_branch:
            try:
                from agent_manager.github import find_pr_for_branch, merge_pull_request, find_merged_pr_for_branch
                pr_num = await find_pr_for_branch(session.repo, session.git_branch)
                if pr_num:
                    logger.info(f"Auto-merging PR #{pr_num} for session {session.session_id} since it's IN_REVIEW.")
                    res = await merge_pull_request(session.repo, pr_num)
                    if res:
                        from agent_manager.poller import LocalGitWatcher
                        watcher = LocalGitWatcher()
                        if session.issue_number:
                            await watcher.update_issue_status(session.repo, session.issue_number, "done")
                        await manager.complete_agent(session.session_id, reason="Auto-merged PR and marked as Done")
                else:
                    merged_num = await find_merged_pr_for_branch(session.repo, session.git_branch)
                    if merged_num:
                        logger.info(f"PR #{merged_num} for session {session.session_id} was already merged on GitHub. Marking as Done.")
                        from agent_manager.poller import LocalGitWatcher
                        watcher = LocalGitWatcher()
                        if session.issue_number:
                            await watcher.update_issue_status(session.repo, session.issue_number, "done")
                        await manager.complete_agent(session.session_id, reason="PR already merged on GitHub")
            except Exception as e:
                logger.error(f"Failed to auto-merge PR or mark issue as done: {e}")

    fire_dispatch_hook()
