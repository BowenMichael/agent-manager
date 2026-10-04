import json
import asyncio
import logging
from pathlib import Path
from typing import Optional

import agent_manager.config as config
from agent_manager.config import (
    WORKSPACE_BASE, AGY_CLI_PATH, AGY_MODE, resolve_model_and_effort
)
from agent_manager.models import AgentStatus, MessageRole
from agent_manager.runners.helpers import get_repository_context
from agent_manager.runners.terminal_launcher import launch_desktop_terminal
from agent_manager.runners.process_manager import launch_detached_agent
from agent_manager.runners.stream_tailer import tail_agent_log

logger = logging.getLogger("agent_manager.runners.orchestrator")


async def run_agent_loop(manager, session_id: str, initial_prompt: str, worktree_path: Optional[str], is_continuation: bool = False):
    session = manager.sessions[session_id]
    try:
        session.status = AgentStatus.RUNNING
        manager._save()
        await manager.broadcast("session_updated", session.model_dump())

        if session.repo and session.issue_number:
            try:
                from agent_manager.poller import LocalGitWatcher
                watcher = LocalGitWatcher()
                asyncio.create_task(watcher.update_issue_status(session.repo, session.issue_number, "in_progress"))
            except Exception as e:
                logger.warning(f"Could not sync Project Board status to in_progress for #{session.issue_number}: {e}")

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

        if current_mode == "terminal":
            existing_proc = manager._active_agents.get(session_id)
            is_proc_alive_status = (existing_proc.poll() is None) if (existing_proc and hasattr(existing_proc, 'poll')) else bool(existing_proc)
            if is_continuation and is_proc_alive_status:
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
            launched = await launch_desktop_terminal(manager, session, issue_num, clean_model, clean_effort, cli_model_args, cwd_dir, target_prompt, is_continuation)
            if launched:
                return
            # Fall back to web_stream mode if terminal launch is not supported on this platform
            logger.info(f"Terminal mode failed/unsupported for session {session_id}; falling back to web_stream mode.")

        prompt_note = f"Prompting agent with model {clean_model} (effort: {clean_effort})" if is_continuation else f"Spawning agent with model {clean_model} (effort: {clean_effort})"
        await manager._append_message(session_id, MessageRole.SYSTEM, f"🌐 [Option 2: Web Stream Override] {prompt_note}...")
        manager._save()
        await manager.broadcast("session_updated", session.model_dump())

        # Setup persistent paths for detached process output and returncode tracking
        logs_dir = Path(cwd_dir) / ".agent_logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = str(logs_dir / f"{session_id}.stream.jsonl")
        exit_file = str(logs_dir / f"{session_id}.exitcode")

        session.stream_log_file = log_file
        session.exit_code_file = exit_file
        if is_continuation and Path(log_file).exists():
            session.stream_log_offset = Path(log_file).stat().st_size
        else:
            session.stream_log_offset = 0

        # Safe fallback when local agy binary is missing (e.g. running in headless Linux container)
        if not Path(AGY_CLI_PATH).exists():
            logger.warning(f"Antigravity CLI binary '{AGY_CLI_PATH}' not found. Emulating graceful headless execution.")
            mock_line = json.dumps({
                "event": "step_update",
                "step_update": {
                    "step_type": "text",
                    "state": "completed",
                    "text": f"⚠️ Antigravity CLI binary not found at '{AGY_CLI_PATH}'. Running in headless fallback mode."
                }
            }) + "\n"
            Path(log_file).write_text(mock_line, encoding="utf-8")
            Path(exit_file).write_text("0", encoding="utf-8")
            session.pid = None
            manager._save()
            await manager.broadcast("session_updated", session.model_dump())
            await tail_agent_log(manager, session_id, clean_model=clean_model)
            return

        cmd_args = [str(AGY_CLI_PATH), *cli_model_args, "--dangerously-skip-permissions", "--output-format", "stream-json"]
        if is_continuation:
            cmd_args.extend(["--continue", "-p", initial_prompt])
        else:
            cmd_args.extend(["-p", agy_prompt])

        pid = launch_detached_agent(cmd_args, cwd=str(cwd_dir), log_file=log_file, exit_file=exit_file)
        session.pid = pid
        manager._save()
        await manager.broadcast("session_updated", session.model_dump())

        await tail_agent_log(manager, session_id, clean_model=clean_model)
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
        manager._save()
