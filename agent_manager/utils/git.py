import asyncio
import logging
from typing import Optional

logger = logging.getLogger("agent_manager.utils.git")

async def get_git_tree(worktree_path: str, max_commits: int = 30) -> str:
    """
    Retrieves the formatted git commit graph/topology for the given worktree path.
    Runs: git log --graph --oneline --decorate --all -n <max_commits>
    """
    if not worktree_path:
        return "No worktree path configured for this session."

    cmd = [
        "git",
        "log",
        "--graph",
        "--oneline",
        "--decorate",
        "--all",
        f"-n{max_commits}",
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=worktree_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            logger.warning(f"git log failed in {worktree_path}: {err_msg}")
            return f"Git error (exit code {proc.returncode}):\n{err_msg}"

        output = stdout.decode(errors="replace").strip()
        return output or "No git commit history found."
    except Exception as e:
        logger.exception(f"Failed to execute git log in {worktree_path}: {e}")
        return f"Error retrieving git tree: {str(e)}"
