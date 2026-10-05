"""
Standalone Agent Worker Service.
Runs as a completely independent OS daemon process, fully detached from the FastAPI web server.
Survives web server restarts, updates, and reloads without interruption.
"""
import os
import sys
import json
import logging
import asyncio
import argparse
import subprocess
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from agent_manager.models import AgentStatus
from agent_manager.storage import load_sessions, save_single_session
from agent_manager.runners.supervisor import post_takeover_notice, sync_issue_board_status, verify_changelog_update
from agent_manager.runners.helpers import get_repository_context
from agent_manager.config import resolve_model_and_effort
from agent_manager.runners.agent_service_pipeline import run_pipeline_in_service
import agent_manager.config as config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AGENT-SERVICE] [%(levelname)s]: %(message)s"
)
logger = logging.getLogger("agent_service")


async def run_independent_agent(session_id: str, is_continuation: bool = False, custom_prompt: Optional[str] = None):
    sessions = load_sessions()
    session = sessions.get(session_id)
    if not session:
        logger.error(f"Session {session_id} not found in persistent storage.")
        sys.exit(1)

    cwd_dir = session.worktree_path or str(config.WORKSPACE_BASE)
    issue_num = session.issue_number or 0
    branch_name = session.git_branch or f"feat/issue-{issue_num}"
    repo = session.repo or config.DEFAULT_REPO

    logger.info(f"Starting independent agent service for Issue #{issue_num} in {cwd_dir} (PID: {os.getpid()})")
    session.status = AgentStatus.RUNNING
    session.pid = os.getpid()
    save_single_session(session)

    # 1. Post Takeover Notice if first turn
    if not is_continuation:
        try:
            await post_takeover_notice(repo, issue_num, cwd_dir, branch_name)
            await sync_issue_board_status(repo, issue_num, "in_progress")
        except Exception as e:
            logger.warning(f"Takeover notice error: {e}")

    # Set up log files
    logs_dir = Path(cwd_dir) / ".agent_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{session_id}.stream.jsonl"
    exit_file = logs_dir / f"{session_id}.exitcode"

    selected_model = session.model or config.DEFAULT_MODEL
    selected_effort = session.effort or config.DEFAULT_EFFORT
    clean_model, clean_effort, cli_model_args = resolve_model_and_effort(selected_model, selected_effort)

    target_prompt = custom_prompt
    if not target_prompt:
        target_prompt = session.messages[-1].content if session.messages else f"Resolve Issue #{issue_num}"

    # Handle pipeline vs direct execution
    if session.workflow_pipeline_enabled and not is_continuation:
        logger.info(f"Executing 3-stage pipeline in independent agent service for {session_id}")
        return_code = await run_pipeline_in_service(session, cwd_dir, issue_num, branch_name, repo, log_file)
    else:
        repo_context = get_repository_context(cwd_dir)
        if is_continuation:
            cmd_args = [
                str(config.AGY_CLI_PATH),
                *cli_model_args,
                "--dangerously-skip-permissions",
                "--output-format", "stream-json",
                "--continue",
                "-p", target_prompt
            ]
        else:
            prompt = (
                f"You are operating autonomously on GitHub Issue #{issue_num} in {repo}.\n"
                f"Working Directory: {cwd_dir}\nGit Branch: {branch_name}\n\n"
                f"### Task Description:\n{target_prompt}\n\n"
                f"### Codebase Context:\n{repo_context}\n\n"
                f"DIRECTIVES:\n"
                f"1. Work strictly in this worktree directory: {cwd_dir}\n"
                f"2. Follow AGENTS.md modular guidelines (keep files under 250 lines).\n"
                f"3. MANDATORY: Update CHANGELOG.md in repo root with your changes.\n"
                f"4. Run unit tests to verify before concluding."
            )
            cmd_args = [
                str(config.AGY_CLI_PATH),
                *cli_model_args,
                "--dangerously-skip-permissions",
                "--output-format", "stream-json",
                "-p", prompt
            ]

        logger.info(f"Executing Antigravity CLI: {' '.join(cmd_args)}")

        if not Path(config.AGY_CLI_PATH).exists():
            mock_line = json.dumps({
                "event": "step_update",
                "step_update": {
                    "step_type": "text",
                    "state": "completed",
                    "text": f"⚠️ Antigravity CLI binary not found at '{config.AGY_CLI_PATH}'. Running in headless fallback mode."
                }
            }) + "\n"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(mock_line)
            return_code = 0
        else:
            with open(log_file, "a", encoding="utf-8", buffering=1) as out_f:
                proc = subprocess.Popen(
                    cmd_args,
                    cwd=str(cwd_dir),
                    stdout=out_f,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL
                )
                return_code = proc.wait()

    exit_file.write_text(str(return_code), encoding="utf-8")
    logger.info(f"CLI execution finished with return code {return_code}")

    # Conclude turn: verify changelog and update status
    sessions = load_sessions()
    session = sessions.get(session_id)
    if session:
        changelog_ok = verify_changelog_update(cwd_dir, branch_name)
        if not changelog_ok:
            logger.warning(f"Agent {session_id} concluded without modifying CHANGELOG.md")
        session.status = AgentStatus.IN_REVIEW
        save_single_session(session)
        try:
            await sync_issue_board_status(repo, issue_num, "in_review")
        except Exception as e:
            logger.warning(f"Error syncing board to in_review: {e}")

    logger.info(f"Independent agent service for session {session_id} finished successfully.")


def main():
    parser = argparse.ArgumentParser(description="Independent Agent Daemon Service")
    parser.add_argument("--session-id", required=True, help="Agent session ID")
    parser.add_argument("--continue", dest="is_continuation", action="store_true", help="Continue existing session")
    parser.add_argument("--prompt", dest="prompt", default=None, help="Custom prompt text")
    args = parser.parse_args()

    asyncio.run(run_independent_agent(args.session_id, is_continuation=args.is_continuation, custom_prompt=args.prompt))


if __name__ == "__main__":
    main()
