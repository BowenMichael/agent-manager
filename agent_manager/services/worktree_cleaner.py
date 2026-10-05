"""
Autonomous Stale Worktree Pruner & Merge Lifecycle Manager.
Safely detects, validates, and prunes merged or stale Git worktrees.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Set, Optional

from agent_manager.runners.process_manager import is_process_alive
from agent_manager.storage import load_sessions

logger = logging.getLogger("agent_manager.services.worktree_cleaner")


def parse_worktree_list(repo_root: Path) -> List[Dict[str, str]]:
    """Runs git worktree list --porcelain and parses path, HEAD, and branch."""
    worktrees = []
    try:
        raw = subprocess.check_output(
            ["git", "worktree", "list", "--porcelain"],
            cwd=str(repo_root),
            text=True,
            stderr=subprocess.STDOUT
        )
        current: Dict[str, str] = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                if current:
                    worktrees.append(current)
                    current = {}
            elif line.startswith("worktree "):
                current["path"] = line.split(" ", 1)[1]
            elif line.startswith("HEAD "):
                current["head"] = line.split(" ", 1)[1]
            elif line.startswith("branch "):
                ref = line.split(" ", 1)[1]
                current["branch"] = ref.replace("refs/heads/", "")
        if current:
            worktrees.append(current)
    except Exception as e:
        logger.warning(f"Failed to list worktrees in {repo_root}: {e}")
    return worktrees


def get_merged_branches(repo_root: Path, base_branch: str = "main") -> Set[str]:
    """Returns the set of local branch names that have been merged into base_branch."""
    try:
        raw = subprocess.check_output(
            ["git", "branch", "--merged", base_branch],
            cwd=str(repo_root),
            text=True,
            stderr=subprocess.STDOUT
        )
        return {b.strip().lstrip("* ") for b in raw.splitlines() if b.strip()}
    except Exception as e:
        logger.warning(f"Failed to query merged branches in {repo_root}: {e}")
        return set()


def get_active_session_worktrees() -> Set[str]:
    """Finds worktree paths currently locked by active running or initializing agents."""
    active_paths: Set[str] = set()
    try:
        sessions = load_sessions().values()
        for sess in sessions:
            if sess.pid and is_process_alive(sess.pid):
                if sess.worktree_path:
                    norm = str(Path(sess.worktree_path).resolve()).lower()
                    active_paths.add(norm)
    except Exception as e:
        logger.warning(f"Error checking active session worktrees: {e}")
    return active_paths


def _prune_single_worktree(repo_root: Path, wt: Dict[str, str], branch: Optional[str]) -> bool:
    """Executes git worktree remove and branch deletion for a single worktree."""
    wt_path = wt.get("path", "")
    try:
        subprocess.check_call(
            ["git", "worktree", "remove", "--force", wt_path],
            cwd=str(repo_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if branch and branch != "main":
            subprocess.call(
                ["git", "branch", "-D", branch],
                cwd=str(repo_root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        return True
    except Exception as e:
        logger.warning(f"Failed to prune worktree {wt_path}: {e}")
        return False


def prune_stale_worktrees(
    repo_root: Optional[Path] = None,
    base_branch: str = "main",
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Scans repository worktrees, cross-references with merged branches,
    and prunes stale worktrees not held by active agent processes.
    """
    root = repo_root or Path(__file__).resolve().parents[2]
    all_worktrees = parse_worktree_list(root)
    merged_branches = get_merged_branches(root, base_branch)
    active_worktrees = get_active_session_worktrees()

    pruned = []
    skipped = []

    for wt in all_worktrees:
        wt_path_str = wt.get("path", "")
        wt_path = Path(wt_path_str).resolve()
        branch = wt.get("branch")

        # Never prune root worktree
        if wt_path == root.resolve():
            continue

        # Never prune worktree outside .worktrees/
        if ".worktrees" not in wt_path_str:
            continue

        norm_path = str(wt_path).lower()
        if norm_path in active_worktrees:
            skipped.append({"path": wt_path_str, "reason": "Active agent process is running"})
            continue

        is_merged = branch in merged_branches if branch else False
        if is_merged:
            if not dry_run:
                success = _prune_single_worktree(root, wt, branch)
                if success:
                    pruned.append({"path": wt_path_str, "branch": branch, "reason": "Merged into main"})
                else:
                    skipped.append({"path": wt_path_str, "reason": "Removal error"})
            else:
                pruned.append({"path": wt_path_str, "branch": branch, "reason": "Merged into main (dry run)"})
        else:
            skipped.append({"path": wt_path_str, "branch": branch, "reason": "Not merged into main"})

    return {
        "repo": str(root),
        "total_worktrees_scanned": len(all_worktrees),
        "pruned_count": len(pruned),
        "pruned": pruned,
        "skipped": skipped,
        "dry_run": dry_run
    }
