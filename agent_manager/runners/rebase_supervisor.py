"""
Multi-Agent Worktree Rebase & Merge Conflict Supervisor.
Automatically detects upstream drift, rebases worktree branches against origin/main,
reconciles non-overlapping diffs, aborts safely on fatal conflicts, and pushes with lease.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import logging
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger("agent_manager.runners.rebase_supervisor")


def _run_git_cmd(cmd: List[str], cwd: Path) -> subprocess.CompletedProcess:
    """Executes a git command in the target directory with timeout."""
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=30)


def check_upstream_drift(worktree_path: Path, base_branch: str = "origin/main") -> Dict[str, Any]:
    """Checks whether the active worktree branch is behind the remote base branch."""
    _run_git_cmd(["git", "fetch", "origin", "main"], worktree_path)
    res = _run_git_cmd(["git", "rev-list", "--count", f"HEAD..{base_branch}"], worktree_path)
    if res.returncode == 0:
        try:
            count = int(res.stdout.strip())
            return {"is_behind": count > 0, "commits_behind": count, "base": base_branch}
        except ValueError:
            pass
    return {"is_behind": False, "commits_behind": 0, "base": base_branch}


def detect_conflicted_files(worktree_path: Path) -> List[str]:
    """Returns list of files currently marked with unmerged git conflicts."""
    res = _run_git_cmd(["git", "diff", "--name-only", "--diff-filter=U"], worktree_path)
    if res.returncode == 0 and res.stdout.strip():
        return [f.strip() for f in res.stdout.strip().splitlines() if f.strip()]
    return []


def resolve_simple_conflicts(file_path: Path) -> bool:
    """Attempts clean automatic resolution of additive conflict markers (e.g. changelog, imports)."""
    try:
        content = file_path.read_text(encoding="utf-8")
        if "<<<<<<<" not in content or "=======" not in content or ">>>>>>>" not in content:
            return False

        # Pattern matches git standard conflict blocks
        conflict_pattern = re.compile(r"<<<<<<<[^\n]*\n(.*?)\n=======\n(.*?)\n>>>>>>>[^\n]*", re.DOTALL)
        def _merge_blocks(match):
            b1 = match.group(1).strip()
            b2 = match.group(2).strip()
            # If both sides are changelog bullets or additions, keep both
            if b1.startswith("-") and b2.startswith("-"):
                return f"{b1}\n{b2}"
            if b1 == b2:
                return b1
            return None

        new_content, count = conflict_pattern.subn(
            lambda m: _merge_blocks(m) if _merge_blocks(m) is not None else m.group(0),
            content
        )
        if count > 0 and "<<<<<<<" not in new_content:
            file_path.write_text(new_content, encoding="utf-8")
            return True
        return False
    except Exception as e:
        logger.warning(f"Error attempting conflict resolution on {file_path}: {e}")
        return False


def abort_rebase(worktree_path: Path) -> None:
    """Safely aborts an active git rebase to restore the worktree to a clean state."""
    _run_git_cmd(["git", "rebase", "--abort"], worktree_path)


def push_with_lease(worktree_path: Path, branch_name: str) -> bool:
    """Safely force-pushes with lease to guarantee remote safety."""
    res = _run_git_cmd(["git", "push", "--force-with-lease", "origin", branch_name], worktree_path)
    return res.returncode == 0


def rebase_worktree(worktree_path: Path, base_branch: str = "origin/main") -> Dict[str, Any]:
    """Rebases worktree branch against upstream base and resolves trivial conflicts."""
    drift = check_upstream_drift(worktree_path, base_branch)
    if not drift.get("is_behind"):
        return {"status": "UP_TO_DATE", "rebased": False, "commits_behind": 0}

    # Attempt rebase
    res = _run_git_cmd(["git", "rebase", base_branch], worktree_path)
    if res.returncode == 0:
        return {"status": "SUCCESS", "rebased": True, "commits_behind": drift["commits_behind"]}

    # Handle conflicts
    conflicted = detect_conflicted_files(worktree_path)
    all_resolved = True
    for f in conflicted:
        resolved = resolve_simple_conflicts(worktree_path / f)
        if resolved:
            _run_git_cmd(["git", "add", f], worktree_path)
        else:
            all_resolved = False

    if all_resolved and conflicted:
        cont_res = _run_git_cmd(["git", "rebase", "--continue"], worktree_path)
        if cont_res.returncode == 0:
            return {"status": "RESOLVED_AUTO", "rebased": True, "conflicted_files": conflicted}

    # If unresolved, abort cleanly
    abort_rebase(worktree_path)
    return {
        "status": "CONFLICT_ABORTED",
        "rebased": False,
        "conflicted_files": conflicted,
        "error": "Semantic merge conflicts require human attention",
    }
