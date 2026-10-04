import json
import logging
from agent_manager.models import MessageRole, AgentStatus
from agent_manager.runners.helpers import format_tool_display, looks_like_quota_error
from agent_manager.utils.command_formatter import format_command_output
import agent_manager.config as config
from agent_manager.github import post_issue_comment
from agent_manager.formatters.comments import (
    format_agent_comment,
    BADGE_AGENT_PAUSED
)

logger = logging.getLogger("agent_manager.runners.stream")


async def handle_tool_call_stream(manager, session, step, sstate, cwd_dir, proc) -> bool:
    tname = step.get("tool_name", "tool")
    tinfo = step.get("tool_info", {})

    if sstate == "ACTIVE":
        tparams = tinfo.get("parameters") or {}
        title_text, desc_text = format_tool_display(tname, tparams)
        session.current_activity = f"Executing: {title_text}"
        await manager._append_message(
            session.session_id,
            MessageRole.TOOL_CALL,
            f"{title_text}\n{desc_text}".strip(),
            tool_name=tname,
            tool_args=tparams
        )

        clean_args = {k: v for k, v in tparams.items() if k not in ("toolAction", "toolSummary")}
        tool_sig = f"{tname}:{json.dumps(clean_args, sort_keys=True)}"

        # 1. Circuit Breaker: Duplicate Consecutive Tool Calls
        if session.last_tool_signature == tool_sig:
            session.consecutive_duplicate_tool_count += 1
        else:
            session.last_tool_signature = tool_sig
            session.consecutive_duplicate_tool_count = 1

        dup_threshold = getattr(config, "CIRCUIT_BREAKER_DUPLICATE_THRESHOLD", 3)
        if getattr(config, "GUARDRAILS_ENABLED", True) and session.consecutive_duplicate_tool_count >= dup_threshold:
            logger.warning(
                f"[Circuit Breaker] Repetitive tool loop detected for session {session.session_id}: "
                f"'{tname}' executed {session.consecutive_duplicate_tool_count} consecutive times with identical arguments."
            )
            session.status = AgentStatus.PAUSED
            session.circuit_breaker_triggered = True
            session.error_message = (
                f"Circuit Breaker Triggered: Repetitive tool loop detected. "
                f"'{tname}' was called {session.consecutive_duplicate_tool_count} consecutive times with identical arguments."
            )
            if proc.returncode is None:
                try:
                    proc.terminate()
                except Exception:
                    pass

            await manager._append_message(
                session.session_id,
                MessageRole.SYSTEM,
                f"🛑 **[Circuit Breaker Triggered: Repetitive Tool Loop]**\n\n"
                f"The agent repeatedly called `{tname}` with identical arguments without making progress:\n"
                f"```json\n{json.dumps(clean_args, indent=2)}\n```\n"
                f"Execution has been safely paused to prevent runaway token spend. "
                f"All worktree files at `{cwd_dir}` are preserved. Review the work and click 'Resume' or provide new instructions."
            )

            if session.issue_number and session.repo:
                try:
                    pause_body = (
                        f"⚠️ **Task Paused: Circuit Breaker Triggered**\n\n"
                        f"### 🛑 Repetitive Tool Loop Detected\n"
                        f"- **Tool**: `{tname}` called {session.consecutive_duplicate_tool_count} consecutive times with identical arguments.\n"
                        f"- **Safeguard**: Execution halted immediately to prevent runaway token consumption.\n"
                        f"- **Worktree**: `{session.worktree_path or cwd_dir}`\n"
                        f"- **Status**: Paused awaiting developer review or resumption."
                    )
                    pause_comment = format_agent_comment(
                        body=pause_body,
                        header=BADGE_AGENT_PAUSED,
                        session_id=session.session_id,
                        worktree_path=session.worktree_path or cwd_dir,
                        git_branch=session.git_branch
                    )
                    comment_res = await post_issue_comment(session.repo, session.issue_number, pause_comment)
                    if comment_res and "id" in comment_res:
                        session.seen_comment_ids.append(str(comment_res["id"]))
                except Exception as e:
                    logger.warning(f"Could not post circuit breaker comment: {e}")

            manager._save()
            await manager.broadcast("session_updated", session.model_dump())
            return True

        # 2. Circuit Breaker: Excessive Consecutive File Reads
        if tname == "view_file":
            session.consecutive_view_file_count += 1
        elif tname in ("replace_file_content", "write_to_file", "multi_replace_file_content", "run_command"):
            session.consecutive_view_file_count = 0

        max_reads_threshold = getattr(config, "CIRCUIT_BREAKER_MAX_CONSECUTIVE_READS", 8)
        if getattr(config, "GUARDRAILS_ENABLED", True) and session.consecutive_view_file_count >= max_reads_threshold:
            logger.warning(
                f"[Circuit Breaker] Excessive consecutive file reads for session {session.session_id}: "
                f"{session.consecutive_view_file_count} consecutive view_file calls without code edits or tests."
            )
            session.status = AgentStatus.PAUSED
            session.circuit_breaker_triggered = True
            session.error_message = (
                f"Circuit Breaker Triggered: Excessive consecutive file reads "
                f"({session.consecutive_view_file_count} view_file calls without editing code or running commands)."
            )
            if proc.returncode is None:
                try:
                    proc.terminate()
                except Exception:
                    pass

            await manager._append_message(
                session.session_id,
                MessageRole.SYSTEM,
                f"🛑 **[Circuit Breaker Triggered: Excessive File Re-Reading]**\n\n"
                f"The agent performed {session.consecutive_view_file_count} consecutive `view_file` calls without making code edits or running tests.\n"
                f"Execution has been safely paused to prevent context saturation and token waste. "
                f"Click 'Resume' or provide specific guidance to proceed."
            )
            manager._save()
            await manager.broadcast("session_updated", session.model_dump())
            return True

        # 3. Turn Budget Guardrail (AGENTS.md Section 2: Max 15 Turns)
        max_turns_limit = getattr(config, "MAX_TURNS_PER_SESSION", 15)
        if getattr(config, "GUARDRAILS_ENABLED", True) and session.turn_count >= max_turns_limit:
            logger.warning(
                f"[Turn Budget Guardrail] Session {session.session_id} reached turn limit ({session.turn_count} / {max_turns_limit}). "
                "Pausing per AGENTS.md budget guardrail."
            )
            session.status = AgentStatus.PAUSED
            session.error_message = f"Turn Budget Limit reached ({session.turn_count} / {max_turns_limit} turns)."
            if proc.returncode is None:
                try:
                    proc.terminate()
                except Exception:
                    pass

            await manager._append_message(
                session.session_id,
                MessageRole.SYSTEM,
                f"⚠️ **[Turn Budget Guardrail Reached]**\n\n"
                f"The agent has reached the maximum budget of **{max_turns_limit} tool execution turns** without completing the task.\n"
                f"Per **AGENTS.md Section 2**, execution is paused to prevent runaway token spend. "
                f"Worktree changes at `{cwd_dir}` are preserved. Review progress and click 'Resume' or provide follow-up instructions."
            )

            if session.issue_number and session.repo:
                try:
                    pause_body = (
                        f"⚠️ **Task Paused: Token / Complexity Budget Threshold Reached**\n\n"
                        f"### 📊 Task Insights\n"
                        f"- **Turns Completed**: {session.turn_count} / {max_turns_limit}\n"
                        f"- **Tokens Recorded**: {session.token_count:,} tokens\n"
                        f"- **Worktree**: `{session.worktree_path or cwd_dir}`\n"
                        f"- **Status**: Paused per AGENTS.md Turn Limit Guardrail (Max {max_turns_limit} turns).\n"
                        f"- **Proposed Next Action**: Review work in worktree and approve continuation from Agent Manager UI or add instructions."
                    )
                    pause_comment = format_agent_comment(
                        body=pause_body,
                        header=BADGE_AGENT_PAUSED,
                        session_id=session.session_id,
                        worktree_path=session.worktree_path or cwd_dir,
                        git_branch=session.git_branch
                    )
                    comment_res = await post_issue_comment(session.repo, session.issue_number, pause_comment)
                    if comment_res and "id" in comment_res:
                        session.seen_comment_ids.append(str(comment_res["id"]))
                except Exception as e:
                    logger.warning(f"Could not post turn budget comment: {e}")

            manager._save()
            await manager.broadcast("session_updated", session.model_dump())
            return True

    elif sstate == "DONE":
        raw_out = tinfo.get("output", "")
        tparams = tinfo.get("parameters") or {}
        if tname == "run_command":
            result_content = format_command_output(tname, raw_out, tparams)
        else:
            out_str = str(raw_out) if raw_out is not None else ""
            if out_str.strip() and out_str.strip() != "Done":
                result_content = out_str
            else:
                title_text, _ = format_tool_display(tname, tparams)
                result_content = f"Completed: {title_text}"
        await manager._append_message(
            session.session_id,
            MessageRole.TOOL_RESULT,
            result_content,
            tool_name=tname
        )

    return False
