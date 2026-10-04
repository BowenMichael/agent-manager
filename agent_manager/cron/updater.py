import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logger = logging.getLogger("agent_manager.cron.updater")


async def check_and_update_agent_manager() -> Dict[str, Any]:
    """
    Checks if agent-manager is on the latest version of main and updates it.
    Rules:
    1. "do this first thing if there are no agents running."
    2. "if there are agents running DO NOT update."
    """
    running_sessions: List[str] = []
    try:
        from agent_manager.runner import AgentRunnerManager
        from agent_manager.models import AgentStatus
        runner = AgentRunnerManager()
        for s in runner.list_sessions():
            if s.status in (AgentStatus.RUNNING, AgentStatus.INITIALIZING):
                running_sessions.append(f"Session {s.session_id} (Issue #{s.issue_number}: {s.title}) [{s.status}]")
        if getattr(runner, "_active_agents", None):
            for sid, proc in runner._active_agents.items():
                if proc and getattr(proc, "returncode", None) is None:
                    running_sessions.append(f"Subprocess for session {sid}")
    except Exception as e:
        logger.warning("[Cron Dispatcher] Could not inspect active runner sessions: %s", e)

    if running_sessions:
        logger.info(
            f"[Cron Dispatcher] Active agent(s) running ({len(running_sessions)} active). "
            "Per guardrail rule: DO NOT UPDATE while agents are running. Skipping update."
        )
        return {
            "checked": True,
            "updated": False,
            "reason": "agents_running",
            "running_agents": running_sessions
        }

    logger.info("[Cron Dispatcher] No agents currently running. Checking if agent-manager is on latest version of main...")
    repo_dir = Path(__file__).resolve().parent.parent.parent

    try:
        fetch_proc = await asyncio.create_subprocess_exec(
            "git", "fetch", "origin", "main",
            cwd=str(repo_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await fetch_proc.communicate()

        rev_local = await asyncio.create_subprocess_exec(
            "git", "rev-parse", "HEAD",
            cwd=str(repo_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        out_local, _ = await rev_local.communicate()
        local_commit = out_local.decode().strip()

        rev_remote = await asyncio.create_subprocess_exec(
            "git", "rev-parse", "origin/main",
            cwd=str(repo_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        out_remote, _ = await rev_remote.communicate()
        remote_commit = out_remote.decode().strip()

        if local_commit == remote_commit:
            logger.info(f"[Cron Dispatcher] agent-manager is already on the latest version of main ({local_commit[:8]}).")
            return {
                "checked": True,
                "updated": False,
                "reason": "already_up_to_date",
                "commit": local_commit
            }

        logger.info(
            f"[Cron Dispatcher] Update available for agent-manager: local={local_commit[:8]} -> remote={remote_commit[:8]}. "
            "Fast-forwarding to latest main..."
        )

        pull_proc = await asyncio.create_subprocess_exec(
            "git", "pull", "--ff-only", "origin", "main",
            cwd=str(repo_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        pull_out, pull_err = await pull_proc.communicate()

        if pull_proc.returncode == 0:
            logger.info(f"[Cron Dispatcher] 🚀 Successfully updated agent-manager to latest main ({remote_commit[:8]}). Output:\n{pull_out.decode().strip()}")
            return {
                "checked": True,
                "updated": True,
                "previous_commit": local_commit,
                "new_commit": remote_commit,
                "output": pull_out.decode().strip()
            }
        else:
            logger.error(f"[Cron Dispatcher] git pull failed (code {pull_proc.returncode}): {pull_err.decode().strip()}")
            return {
                "checked": True,
                "updated": False,
                "reason": "pull_failed",
                "error": pull_err.decode().strip()
            }

    except Exception as e:
        logger.error(f"[Cron Dispatcher] Error during git check/update: {e}", exc_info=True)
        return {"checked": True, "updated": False, "reason": "error", "error": str(e)}
