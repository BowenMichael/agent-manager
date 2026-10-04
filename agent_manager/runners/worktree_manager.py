import subprocess
import logging
from typing import Optional
from pathlib import Path
from agent_manager.utils.workspace import find_local_workspace

logger = logging.getLogger("agent_manager.runners.worktree")


def setup_worktree(repo: str, issue_number: int) -> tuple[Optional[str], Optional[str]]:
    """Sets up isolated git worktree for the issue to prevent branch conflicts."""
    repo_dir = find_local_workspace(repo)

    if not repo_dir:
        logger.warning(f"No git repository found for {repo}. Operating without isolated worktree.")
        return None, None

    worktrees_dir = repo_dir / ".worktrees"
    worktrees_dir.mkdir(parents=True, exist_ok=True)
    worktree_path = worktrees_dir / f"issue-{issue_number}"
    branch_name = f"feat/issue-{issue_number}"

    try:
        if not worktree_path.exists():
            cmd = f'git worktree add -B "{branch_name}" "{worktree_path}" origin/main'
            res = subprocess.run(cmd, cwd=str(repo_dir), shell=True, capture_output=True, text=True)
            if res.returncode != 0:
                cmd_fallback = f'git worktree add -B "{branch_name}" "{worktree_path}" HEAD'
                subprocess.run(cmd_fallback, cwd=str(repo_dir), shell=True, capture_output=True, text=True)
        return str(worktree_path), branch_name
    except Exception as e:
        logger.error(f"Failed to create worktree: {e}")
        return None, None
