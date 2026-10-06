"""
Pipeline executor for standalone agent daemon service.
Runs multi-stage agent workflows (Summarize -> Plan -> Implement) independently from the web server.
"""
import os
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

from agent_manager.models import WorkflowStage, MessageRole, ConversationMessage
from agent_manager.storage import save_single_session
from agent_manager.runners.helpers import get_repository_context
from agent_manager.config import resolve_model_and_effort
import agent_manager.config as config

logger = logging.getLogger("agent_service.pipeline")


def _run_stage_cli(cmd_args: list, cwd: str, log_file: Path) -> int:
    """Executes a single CLI turn piping output to log_file."""
    with open(log_file, "a", encoding="utf-8", buffering=1) as out_f:
        proc = subprocess.Popen(
            cmd_args,
            cwd=str(cwd),
            stdout=out_f,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL
        )
        return proc.wait()


def _append_stream_event(log_file: Path, text: str):
    """Appends a synthetic step event to the stream log so UI observes stage transition."""
    ev = {
        "event": "step_update",
        "step_update": {
            "step_type": "text",
            "state": "completed",
            "text": text
        }
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev) + "\n")


async def run_pipeline_in_service(session, cwd_dir: str, issue_num: int, branch_name: str, repo: str, log_file: Path) -> int:
    """Executes the 3-stage pipeline inside the independent daemon service."""
    sum_model = getattr(config, "PIPELINE_SUMMARY_MODEL", "gemini-3.8-flash")
    sum_effort = getattr(config, "PIPELINE_SUMMARY_EFFORT", "low")
    plan_model = getattr(config, "PIPELINE_PLANNING_MODEL", "gemini-3.1-pro")
    plan_effort = getattr(config, "PIPELINE_PLANNING_EFFORT", "high")
    impl_model = getattr(config, "PIPELINE_IMPLEMENTATION_MODEL", "gemini-3.8-flash")
    impl_effort = getattr(config, "PIPELINE_IMPLEMENTATION_EFFORT", "high")

    initial_prompt = session.messages[0].content if session.messages else f"Resolve Issue #{issue_num}"

    # STAGE 1: ISSUE SUMMARY
    session.workflow_stage = WorkflowStage.SUMMARIZING
    session.model = sum_model
    session.effort = sum_effort
    session.current_activity = f"Stage 1/3: Summarizing requirements ({sum_model} / {sum_effort})..."
    save_single_session(session)
    _append_stream_event(log_file, f"🔄 **Pipeline Stage 1/3: Issue Summarization** (`{sum_model}` / `{sum_effort}`)")

    _, _, sum_cli_args = resolve_model_and_effort(sum_model, sum_effort)
    summary_prompt = (
        f"You are a requirements analyst. Read the following task description for GitHub Issue #{issue_num} in {repo}:\n\n"
        f"{initial_prompt}\n\n"
        f"Provide a structured summary:\n1. Core Objective\n2. Acceptance Criteria & Requirements\n3. Key Constraints & Context\n"
        f"Keep the summary concise."
    )
    cmd_s1 = [str(config.AGY_CLI_PATH), *sum_cli_args, "--dangerously-skip-permissions", "--output-format", "stream-json", "-p", summary_prompt]
    rc1 = _run_stage_cli(cmd_s1, cwd_dir, log_file)
    if rc1 != 0:
        logger.warning(f"Stage 1 summary exited with code {rc1}")

    # STAGE 2: ARCHITECTURAL PLANNING
    session.workflow_stage = WorkflowStage.PLANNING
    session.model = plan_model
    session.effort = plan_effort
    session.current_activity = f"Stage 2/3: Formulating plan ({plan_model} / {plan_effort})..."
    save_single_session(session)
    _append_stream_event(log_file, f"🧠 **Pipeline Stage 2/3: High-Reasoning Planning** (`{plan_model}` / `{plan_effort}`)")

    repo_context = get_repository_context(cwd_dir, query=initial_prompt)
    _, _, plan_cli_args = resolve_model_and_effort(plan_model, plan_effort)
    planning_prompt = (
        f"You are a principal software architect. Formulate the implementation plan for GitHub Issue #{issue_num} in {cwd_dir}.\n\n"
        f"### Task Description:\n{initial_prompt}\n\n"
        f"### Codebase Context:\n{repo_context}\n\n"
        f"Provide a structured plan with: 1. Architecture Overview, 2. Target Files (keep files under 250 lines), "
        f"3. Step-by-Step Implementation Guide, 4. Verification & Testing Criteria, 5. Updating CHANGELOG.md under [Unreleased]."
    )
    cmd_s2 = [str(config.AGY_CLI_PATH), *plan_cli_args, "--dangerously-skip-permissions", "--output-format", "stream-json", "--continue", "-p", planning_prompt]
    rc2 = _run_stage_cli(cmd_s2, cwd_dir, log_file)
    if rc2 != 0:
        logger.warning(f"Stage 2 plan exited with code {rc2}")

    # STAGE 3: IMPLEMENTATION
    session.workflow_stage = WorkflowStage.IMPLEMENTING
    session.model = impl_model
    session.effort = impl_effort
    session.current_activity = f"Stage 3/3: Implementing code ({impl_model} / {impl_effort})..."
    save_single_session(session)
    _append_stream_event(log_file, f"⚡ **Pipeline Stage 3/3: Implementation** (`{impl_model}` / `{impl_effort}`)")

    _, _, impl_cli_args = resolve_model_and_effort(impl_model, impl_effort)
    impl_prompt = (
        f"Execute the approved plan for GitHub Issue #{issue_num} in worktree {cwd_dir}.\n"
        f"Directives: Keep files under 250 lines. Run unit tests to verify. Update CHANGELOG.md in repo root before finishing."
    )
    cmd_s3 = [str(config.AGY_CLI_PATH), *impl_cli_args, "--dangerously-skip-permissions", "--output-format", "stream-json", "--continue", "-p", impl_prompt]
    return _run_stage_cli(cmd_s3, cwd_dir, log_file)
