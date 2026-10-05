import logging
from agent_manager.models import WorkflowStage, MessageRole
from agent_manager.runners.helpers import get_repository_context
import agent_manager.config as config
from agent_manager.config import (
    PIPELINE_SUMMARY_MODEL, PIPELINE_SUMMARY_EFFORT,
    PIPELINE_PLANNING_MODEL, PIPELINE_PLANNING_EFFORT,
    PIPELINE_IMPLEMENTATION_MODEL, PIPELINE_IMPLEMENTATION_EFFORT
)

logger = logging.getLogger("agent_manager.runners.pipeline")


async def run_workflow_pipeline(manager, session_id: str, task_description: str, cwd_dir: str, issue_num: int, branch_name: str):
    session = manager.sessions[session_id]

    sum_model = getattr(config, "PIPELINE_SUMMARY_MODEL", PIPELINE_SUMMARY_MODEL)
    sum_effort = getattr(config, "PIPELINE_SUMMARY_EFFORT", PIPELINE_SUMMARY_EFFORT)
    plan_model = getattr(config, "PIPELINE_PLANNING_MODEL", PIPELINE_PLANNING_MODEL)
    plan_effort = getattr(config, "PIPELINE_PLANNING_EFFORT", PIPELINE_PLANNING_EFFORT)
    impl_model = getattr(config, "PIPELINE_IMPLEMENTATION_MODEL", PIPELINE_IMPLEMENTATION_MODEL)
    impl_effort = getattr(config, "PIPELINE_IMPLEMENTATION_EFFORT", PIPELINE_IMPLEMENTATION_EFFORT)

    # STAGE 1: ISSUE SUMMARY (Dumb Model)
    session.workflow_stage = WorkflowStage.SUMMARIZING
    session.model = sum_model
    session.effort = sum_effort
    session.current_activity = f"Stage 1/3: Summarizing requirements ({sum_model} / {sum_effort})..."
    await manager._append_message(
        session_id,
        MessageRole.SYSTEM,
        f"🔄 **Pipeline Stage 1/3: Issue Summarization**\n"
        f"Using model: `{sum_model}` (effort: `{sum_effort}`)\n"
        f"Extracting core objectives, acceptance criteria, and constraints from Issue #{issue_num}..."
    )
    manager._save()
    await manager.broadcast("session_updated", session.model_dump())

    summary_prompt = (
        f"You are a requirements analyst. Read the following GitHub issue task description:\n\n"
        f"{task_description}\n\n"
        f"Provide a clear, structured summary:\n"
        f"1. Core Objective\n"
        f"2. Acceptance Criteria & Requirements\n"
        f"3. Key Constraints & Context\n"
        f"Keep the summary concise and focused."
    )
    summary_result = await manager._run_cli_turn(session_id, summary_prompt, cwd_dir, sum_model, sum_effort)
    session.pipeline_summary = summary_result or "Summary completed."
    await manager._append_message(
        session_id,
        MessageRole.AGENT,
        f"📋 **Stage 1 Summary Deliverable**:\n\n{session.pipeline_summary}"
    )
    manager._save()
    await manager.broadcast("session_updated", session.model_dump())

    # STAGE 2: ARCHITECTURAL PLANNING (Smart Model)
    session.workflow_stage = WorkflowStage.PLANNING
    session.model = plan_model
    session.effort = plan_effort
    session.current_activity = f"Stage 2/3: Formulating plan ({plan_model} / {plan_effort})..."

    repo_context = get_repository_context(cwd_dir)

    await manager._append_message(
        session_id,
        MessageRole.SYSTEM,
        f"🧠 **Pipeline Stage 2/3: High-Reasoning Planning**\n\n"
        f"**Model**: `{plan_model}` (effort: `{plan_effort}`)\n"
        f"**Context Injected**: Directory manifest, configuration files, and git history from `{cwd_dir}`.\n\n"
        f"Formulating architectural execution plan based on Stage 1 summary and repository structure..."
    )
    manager._save()
    await manager.broadcast("session_updated", session.model_dump())

    planning_prompt = (
        f"You are a principal software architect. You are formulating the high-level implementation strategy for GitHub Issue #{issue_num} in {cwd_dir}.\n\n"
        f"### Issue Requirements Summary:\n{session.pipeline_summary}\n\n"
        f"### Original Task Description:\n{task_description}\n\n"
        f"### Codebase Context (Repository Structure & Configurations):\n{repo_context}\n\n"
        f"**PLANNING DIRECTIVE (Architectural Guidance over Code Implementation)**:\n"
        f"- DO NOT write full code implementations, function bodies, or large code diffs in this plan.\n"
        f"- Focus on high-level architectural design, system boundaries, and clear step-by-step instructions.\n"
        f"- Give Stage 3 (the implementation model) all the structural guidance, file targets, and verification criteria it needs so it can write the code itself.\n\n"
        f"Provide a structured plan containing:\n"
        f"1. **Architectural Overview**: Conceptual approach, component interactions, and key design decisions.\n"
        f"2. **Target Files & Modular Breakdown**: Exact files to create or modify. STRICT ANTI-MONOLITH RULE: Keep all files under 250 lines; decompose into dedicated modular files (`models/`, `services/`, `components/`, `utils/`).\n"
        f"3. **Step-by-Step Implementation Guide**: Clear, ordered instructions specifying WHAT each component must accomplish without writing full code blocks.\n"
        f"4. **Verification & Testing Criteria**: Expected behavior, test commands to run, and verification checklist (with command log suppression).\n"
        f"5. **Documentation & Changelog**: Specify updating `CHANGELOG.md` with new entries under `[Unreleased]` linked to Issue #{issue_num} (initialize file if missing)."
    )
    plan_result = await manager._run_cli_turn(session_id, planning_prompt, cwd_dir, plan_model, plan_effort)
    session.pipeline_plan = plan_result or "Plan formulated."
    await manager._append_message(
        session_id,
        MessageRole.AGENT,
        f"📐 **Stage 2 Plan Deliverable**:\n\n{session.pipeline_plan}"
    )
    manager._save()
    await manager.broadcast("session_updated", session.model_dump())

    # STAGE 3: IMPLEMENTATION (Dumb Model)
    session.workflow_stage = WorkflowStage.IMPLEMENTING
    session.model = impl_model
    session.effort = impl_effort
    session.current_activity = f"Stage 3/3: Implementing code ({impl_model} / {impl_effort})..."
    await manager._append_message(
        session_id,
        MessageRole.SYSTEM,
        f"⚡ **Pipeline Stage 3/3: Execution & Implementation**\n"
        f"Using implementation model: `{impl_model}` (effort: `{impl_effort}`)\n"
        f"Executing changes in isolated worktree `{cwd_dir}` according to the plan..."
    )
    manager._save()
    await manager.broadcast("session_updated", session.model_dump())

    implementation_prompt = (
        f"You are operating autonomously on GitHub Issue #{issue_num}.\n"
        f"Working Directory: {cwd_dir}\n"
        f"Git Branch: {branch_name}\n\n"
        f"### Approved Implementation Plan:\n{session.pipeline_plan}\n\n"
        f"### Issue Context & Summary:\n{session.pipeline_summary}\n\n"
        f"Execute the steps in the plan now. Modify the required files, run unit tests to verify, and summarize your completed work.\n"
        f"Follow AGENTS.md conventions, and update CHANGELOG.md in the repo root before concluding or opening a PR."
    )

    import subprocess
    max_verification_attempts = 3
    for attempt in range(max_verification_attempts):
        await manager._run_agent_loop(session_id, implementation_prompt, cwd_dir, is_continuation=True)
        
        try:
            # Algorithmic Verification: Did they update CHANGELOG.md?
            diff_output = subprocess.check_output(
                ["git", "diff", "--name-only", "main", branch_name], 
                cwd=cwd_dir, 
                text=True
            )
            if "CHANGELOG.md" in diff_output:
                logger.info(f"Session {session_id} passed programmatic validation for CHANGELOG.md")
                break
            else:
                failure_msg = "Validation Failed: You did not update CHANGELOG.md. Please update it before finishing."
                await manager._append_message(session_id, MessageRole.SYSTEM, f"🛑 **{failure_msg}**")
                implementation_prompt = f"You failed the programmatic validation. {failure_msg}\n\nPlease fix this and conclude."
                manager._save()
                await manager.broadcast("session_updated", session.model_dump())
        except Exception as e:
            logger.error(f"Failed to verify changelog algorithmically: {e}")
            break
