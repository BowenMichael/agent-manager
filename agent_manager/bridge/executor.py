"""
Local Worktree Execution Engine for Workstation Bridge.
Spawns local Antigravity CLI (agy) or runner within isolated Git worktrees.
Streams tokens, diffs, and thoughts back to the bridge daemon.
Adheres strictly to Anti-Monolith guidelines (< 250 lines, < 40 lines per function).
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, Optional

from agent_manager.bridge.models import (
    WorkstationTaskRequest,
    WorkstationStreamChunk,
    WorkstationTaskResult,
)

logger = logging.getLogger("agent_manager.bridge.executor")


class LocalWorktreeExecutor:
    """Executes agent runs within isolated local git worktrees."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()

    def prepare_worktree_path(self, task: WorkstationTaskRequest) -> Path:
        """Determines or creates the target worktree path for the issue."""
        if task.worktree_path:
            return Path(task.worktree_path)
        return self.workspace_root / ".worktrees" / f"issue-{task.issue_number}"

    def build_command(self, task: WorkstationTaskRequest, worktree_dir: Path) -> list[str]:
        """Constructs the command to execute the agent."""
        if task.command_override:
            return task.command_override.split()
        return [
            sys.executable,
            "-m", "agent_manager.runner",
            "--task", task.task_description,
            "--repo", task.repo,
            "--issue", str(task.issue_number)
        ]

    async def execute_task_stream(
        self,
        task: WorkstationTaskRequest,
        workstation_id: str
    ) -> AsyncGenerator[WorkstationStreamChunk, None]:
        """Runs the task and yields streaming chunks as execution proceeds."""
        worktree_dir = self.prepare_worktree_path(task)
        cmd = self.build_command(task, worktree_dir)
        
        yield WorkstationStreamChunk(
            task_id=task.task_id,
            workstation_id=workstation_id,
            chunk_type="status",
            payload={"status": "starting", "worktree": str(worktree_dir), "cmd": cmd}
        )

        try:
            async for chunk in self._run_process_and_yield(task, workstation_id, cmd, worktree_dir):
                yield chunk
        except Exception as exc:
            logger.exception(f"Execution error for task {task.task_id}: {exc}")
            yield WorkstationStreamChunk(
                task_id=task.task_id,
                workstation_id=workstation_id,
                chunk_type="error",
                payload={"error": str(exc), "success": False}
            )

    async def _run_process_and_yield(
        self,
        task: WorkstationTaskRequest,
        workstation_id: str,
        cmd: list[str],
        worktree_dir: Path
    ) -> AsyncGenerator[WorkstationStreamChunk, None]:
        """Spawns process, streams output, and yields final exit status."""
        env = self._prepare_env(task)
        cwd = str(worktree_dir) if worktree_dir.exists() else str(self.workspace_root)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env
        )
        async for chunk in self._stream_process_output(proc, task.task_id, workstation_id):
            yield chunk
        exit_code = await proc.wait()
        success = (exit_code == 0)
        yield WorkstationStreamChunk(
            task_id=task.task_id,
            workstation_id=workstation_id,
            chunk_type="complete" if success else "error",
            payload={"exit_code": exit_code, "success": success}
        )

    async def _stream_process_output(
        self,
        proc: asyncio.subprocess.Process,
        task_id: str,
        workstation_id: str
    ) -> AsyncGenerator[WorkstationStreamChunk, None]:
        """Streams stdout and stderr line by line."""
        while True:
            line = await proc.stdout.readline() if proc.stdout else b""
            if not line:
                break
            text = line.decode("utf-8", errors="replace").strip()
            if text:
                yield WorkstationStreamChunk(
                    task_id=task_id,
                    workstation_id=workstation_id,
                    chunk_type="stdout",
                    payload={"text": text}
                )

    def _prepare_env(self, task: WorkstationTaskRequest) -> Dict[str, str]:
        """Prepares environment variables for the subagent run."""
        env = os.environ.copy()
        if task.environment:
            env.update(task.environment)
        if task.auth_token:
            env["AGENT_MANAGER_TOKEN"] = task.auth_token
        return env
