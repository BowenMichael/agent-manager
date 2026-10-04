import json
import asyncio
import logging
from typing import Optional

import agent_manager.config as config
from agent_manager.config import (
    WORKSPACE_BASE, AGY_CLI_PATH, AGY_MODE, MAX_SESSION_TOKENS, resolve_model_and_effort
)
from agent_manager.models import AgentStatus, MessageRole
from agent_manager.runners.helpers import (
    looks_like_quota_error, get_repository_context
)
from agent_manager.runners.stream_handler import handle_tool_call_stream
from agent_manager.runners.terminal_launcher import launch_desktop_terminal
from agent_manager.runners.post_turn import handle_turn_completion, handle_post_process

logger = logging.getLogger("agent_manager.runners.orchestrator")


async def run_agent_loop(manager, session_id: str, initial_prompt: str, worktree_path: Optional[str], is_continuation: bool = False):
    session = manager.sessions[session_id]
    try:
        session.status = AgentStatus.RUNNING
        manager._save()
        cwd_dir = worktree_path or str(WORKSPACE_BASE)
        issue_num = session.issue_number or 0
        branch_name = session.git_branch or f"feat/issue-{issue_num}"

        if session.workflow_pipeline_enabled and not is_continuation:
            await manager._run_workflow_pipeline(session_id, initial_prompt, cwd_dir, issue_num, branch_name)
            return

        selected_model = session.model or getattr(config, "DEFAULT_MODEL", "gemini-3.8-flash")
        selected_effort = session.effort or getattr(config, "DEFAULT_EFFORT", "high")
        clean_model, clean_effort, cli_model_args = resolve_model_and_effort(selected_model, selected_effort)
        session.model = clean_model
        session.effort = clean_effort

        current_mode = getattr(config, "AGY_MODE", AGY_MODE)
        current_max_tokens = getattr(config, "MAX_SESSION_TOKENS", MAX_SESSION_TOKENS)

        if current_mode == "terminal":
            existing_proc = manager._active_agents.get(session_id)
            is_proc_alive = (existing_proc.poll() is None) if (existing_proc and hasattr(existing_proc, 'poll')) else bool(existing_proc)
            if is_continuation and is_proc_alive:
                session.status = AgentStatus.IN_REVIEW
                await manager._append_message(session_id, MessageRole.SYSTEM, f"⚡ [Option 1: Interactive Desktop Terminal] Active terminal retained for session at {cwd_dir}.")
                manager._save()
                await manager.broadcast("session_updated", session.model_dump())
                return

        repo_context = get_repository_context(cwd_dir)
        agy_prompt = (
            f"You are operating autonomously on GitHub Issue #{issue_num}.\n"
            f"Working Directory: {cwd_dir}\nGit Branch: {branch_name}\n\nTask Description:\n{initial_prompt}\n\n"
            f"Codebase Context (Repository Structure & Configurations):\n{repo_context}\n\n"
            f"RULES & EFFICIENCY GUARDRAILS:\n1. Make changes in this directory.\n2. Follow AGENTS.md conventions.\n"
            f"3. CRITICAL TOOL EFFICIENCY: SEARCH FIRST, SLICE READING ONLY (max 100 lines), NEVER RE-READ.\n"
            f"4. ANTI-MONOLITH RULE: Keep files under 250 LOC.\n"
            f"5. Board status columns are managed directly.\n"
        )

        if current_mode == "terminal":
            target_prompt = initial_prompt if is_continuation else agy_prompt
            await launch_desktop_terminal(manager, session, issue_num, clean_model, clean_effort, cli_model_args, cwd_dir, target_prompt, is_continuation)
            return

        prompt_note = f"Prompting agent with model {clean_model} (effort: {clean_effort})" if is_continuation else f"Spawning agent with model {clean_model} (effort: {clean_effort})"
        await manager._append_message(session_id, MessageRole.SYSTEM, f"🌐 [Option 2: Web Stream Override] {prompt_note}...")
        manager._save()
        await manager.broadcast("session_updated", session.model_dump())

        cmd_args = [str(AGY_CLI_PATH), *cli_model_args, "--dangerously-skip-permissions", "--output-format", "stream-json"]
        if is_continuation:
            cmd_args.extend(["--continue", "-p", initial_prompt])
        else:
            cmd_args.extend(["-p", agy_prompt])

        proc = await asyncio.create_subprocess_exec(*cmd_args, cwd=str(cwd_dir), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        manager._active_agents[session_id] = proc

        while True:
            line_bytes = await proc.stdout.readline()
            if not line_bytes:
                break
            line_str = line_bytes.decode('utf-8', errors='replace').strip()
            if not line_str:
                continue
            try:
                event_obj = json.loads(line_str)
                ev = event_obj.get("event")
                if ev == "step_update":
                    session.is_stalled = False
                    step = event_obj.get("step_update", {})
                    stype = step.get("step_type")
                    sstate = step.get("state")

                    usage = step.get("usage")
                    if usage:
                        session.input_tokens = usage.get("input_tokens", session.input_tokens)
                        session.output_tokens = usage.get("output_tokens", session.output_tokens)
                        session.thinking_tokens = usage.get("thinking_tokens", session.thinking_tokens)
                        session.cache_read_tokens = usage.get("cache_read_tokens", session.cache_read_tokens)
                        session.total_tokens = usage.get("total_tokens", session.total_tokens)
                        session.token_count = session.total_tokens
                        session.max_tokens = current_max_tokens
                        session.quota_percent = min(100.0, round((session.total_tokens / current_max_tokens) * 100, 1))

                        if getattr(config, "GUARDRAILS_ENABLED", True) and session.total_tokens >= current_max_tokens:
                            session.status = AgentStatus.PAUSED
                            session.error_message = f"Token budget limit reached ({session.total_tokens:,} / {current_max_tokens:,} tokens)."
                            if proc.returncode is None:
                                proc.terminate()
                            manager._save()
                            await manager.broadcast("session_updated", session.model_dump())
                            return

                        manager._save()
                        await manager.broadcast("session_updated", session.model_dump())

                    if stype == "tool":
                        interrupted = await handle_tool_call_stream(manager, session, step, sstate, cwd_dir, proc)
                        if interrupted:
                            return
                    elif stype == "agent_response":
                        delta = step.get("text_delta")
                        if delta:
                            await manager._broadcast_token(session_id, delta)
                        if sstate == "DONE" and delta:
                            await manager._append_message(session_id, MessageRole.AGENT, delta)
                elif ev == "result":
                    res_info = event_obj.get("result", {})
                    final_resp = res_info.get("response", "Agent finished task.")
                    final_usage = res_info.get("usage")
                    if final_usage:
                        session.input_tokens = final_usage.get("input_tokens", session.input_tokens)
                        session.output_tokens = final_usage.get("output_tokens", session.output_tokens)
                        session.thinking_tokens = final_usage.get("thinking_tokens", session.thinking_tokens)
                        session.cache_read_tokens = final_usage.get("cache_read_tokens", session.cache_read_tokens)
                        session.total_tokens = final_usage.get("total_tokens", session.total_tokens)
                        session.token_count = session.total_tokens
                    await handle_turn_completion(manager, session, final_resp)
                elif ev == "error" or event_obj.get("error"):
                    err_txt = json.dumps(event_obj.get("error", event_obj))
                    if looks_like_quota_error(err_txt):
                        await manager._flag_quota_exceeded(session_id, err_txt)
            except json.JSONDecodeError:
                if looks_like_quota_error(line_str):
                    await manager._flag_quota_exceeded(session_id, line_str)
            except Exception as json_err:
                logger.debug(f"JSON stream line parse info: {json_err}")

        await proc.wait()
        try:
            stderr_txt = (await proc.stderr.read()).decode("utf-8", errors="replace")
        except Exception:
            stderr_txt = ""
        if proc.returncode != 0 and looks_like_quota_error(stderr_txt):
            await manager._flag_quota_exceeded(session_id, stderr_txt)
        if proc.returncode != 0 and stderr_txt.strip():
            await manager._append_message(session_id, MessageRole.SYSTEM, f"Agent CLI exited with code {proc.returncode}: {stderr_txt.strip()[-800:]}")

        try:
            from agent_manager.telemetry import record_token_usage
            record_token_usage(
                session_id=session_id,
                repo=session.repo or "",
                model=session.model or clean_model,
                input_tokens=session.input_tokens,
                output_tokens=session.output_tokens,
                thinking_tokens=session.thinking_tokens,
                cache_read_tokens=session.cache_read_tokens,
                total_tokens=session.total_tokens
            )
        except Exception:
            pass

        await handle_post_process(manager, session, proc)
        manager._save()
        await manager.broadcast("session_updated", session.model_dump())
        return
    except asyncio.CancelledError:
        if session.status != AgentStatus.COMPLETED:
            session.status = AgentStatus.STOPPED
        logger.info(f"Agent session {session_id} task was cancelled.")
    except Exception as e:
        session.status = AgentStatus.FAILED
        session.error_message = str(e)
        logger.exception(f"Error during agent session {session_id}: {e}")
        await manager._append_message(session_id, MessageRole.SYSTEM, f"Agent encountered error: {str(e)}")
    finally:
        curr_mode = getattr(config, "AGY_MODE", AGY_MODE)
        if curr_mode != "terminal":
            manager._active_agents.pop(session_id, None)
        manager._save()
