import os
import configparser
import logging
from pathlib import Path
from typing import Optional

from agent_manager.config import WORKSPACE_BASE

logger = logging.getLogger("agent_manager.utils.workspace")


def _is_matching_repo(repo_path: Path, repo_full_name: str) -> bool:
    """
    Checks if a given local directory is a git repository matching repo_full_name
    by inspecting its git configuration remote origin URL.
    """
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        return False

    config_path = git_dir / "config" if git_dir.is_dir() else None
    # Support git worktrees or submodules where .git might be a file
    if git_dir.is_file():
        try:
            content = git_dir.read_text(encoding="utf-8", errors="replace").strip()
            if content.startswith("gitdir:"):
                actual_git_dir = Path(content.split("gitdir:", 1)[1].strip())
                if not actual_git_dir.is_absolute():
                    actual_git_dir = (repo_path / actual_git_dir).resolve()
                config_path = actual_git_dir / "config"
        except Exception:
            pass

    if not config_path or not config_path.exists():
        return False

    try:
        config = configparser.ConfigParser()
        config.read(config_path, encoding="utf-8")
        target_normalized = repo_full_name.lower().strip()
        for section in config.sections():
            if section.startswith('remote "'):
                url = config[section].get("url", "").lower()
                # Match URL variations:
                # https://github.com/BowenMichael/agent-manager.git
                # git@github.com:BowenMichael/agent-manager.git
                # BowenMichael/agent-manager
                if target_normalized in url.replace(".git", ""):
                    return True
    except Exception as e:
        logger.debug(f"Failed to parse git config at {config_path}: {e}")

    return False


def find_local_workspace(repo_full_name: str) -> Optional[Path]:
    """
    Dynamically resolves and validates the local git workspace path corresponding to
    a target repository (e.g. 'BowenMichael/agent-manager' or 'BowenMichael/f1-frontend').

    Searches:
    1. Current working directory and immediate parent checkouts.
    2. WORKSPACE_BASE direct child matching the repo name.
    3. Nested subdirectories under WORKSPACE_BASE (bounded to depth <= 3).

    Returns the validated Path if found, or None.
    """
    if not repo_full_name or not str(repo_full_name).strip():
        return None

    repo_full_name = str(repo_full_name).strip()
    repo_name = repo_full_name.split("/")[-1].strip()

    # 1. Fast path: check current working directory
    try:
        cwd = Path.cwd().resolve()
        if (cwd / ".git").exists() and (
            cwd.name.lower() == repo_name.lower() or _is_matching_repo(cwd, repo_full_name)
        ):
            return cwd
        # If in a worktree (.worktrees/issue-X), check the parent repo root
        if cwd.parent.name == ".worktrees" and (cwd.parent.parent / ".git").exists():
            parent_repo = cwd.parent.parent
            if parent_repo.name.lower() == repo_name.lower() or _is_matching_repo(parent_repo, repo_full_name):
                return parent_repo
    except Exception:
        pass

    # 2. Check WORKSPACE_BASE
    base = Path(WORKSPACE_BASE).resolve()
    if not base.exists():
        logger.warning(f"WORKSPACE_BASE '{base}' does not exist.")
        return None

    # Direct match in WORKSPACE_BASE
    direct_path = base / repo_name
    if direct_path.exists() and (direct_path / ".git").exists():
        if _is_matching_repo(direct_path, repo_full_name):
            return direct_path

    # Search WORKSPACE_BASE subdirectories bounded by max depth 3
    candidate_match_by_name = []
    excluded_dirs = {
        ".git", ".worktrees", "node_modules", "dist", "build",
        "__pycache__", ".venv", "venv", ".next", ".cache"
    }

    try:
        for root, dirs, files in os.walk(base):
            root_path = Path(root)

            # Filter out excluded directories in-place
            dirs[:] = [d for d in dirs if d not in excluded_dirs and not d.startswith(".")]

            # Compute depth relative to base
            try:
                rel_parts = root_path.relative_to(base).parts
                depth = len(rel_parts)
            except ValueError:
                depth = 0

            # Prune search beyond depth 3
            if depth >= 3:
                dirs.clear()

            if root_path.name.lower() == repo_name.lower() and (root_path / ".git").exists():
                if _is_matching_repo(root_path, repo_full_name):
                    return root_path
                candidate_match_by_name.append(root_path)
    except Exception as e:
        logger.error(f"Error while scanning workspaces under {base}: {e}")

    # Fallback to direct candidate by directory name if remote didn't explicitly match
    if candidate_match_by_name:
        return candidate_match_by_name[0]

    if direct_path.exists() and (direct_path / ".git").exists():
        return direct_path

    logger.warning(f"No local checkout found for repository '{repo_full_name}' under '{base}'.")
    return None
