import logging
import asyncio
import subprocess
from typing import Optional, Dict, Any
from pathlib import Path

from agent_manager.models import AgentStatus, MessageRole, SpawnRequest
from agent_manager.github import post_issue_comment, find_pr_for_branch
import agent_manager.config as config

logger = logging.getLogger("agent_manager.supervisor")


async def post_takeover_notice(repo: str, issue_number: int, worktree_path: str, branch_name: str) -> None:
    comment_body = (
        f"🤖 **Agent Takeover: Development Started**\n\n"
        f"- **Worktree**: {worktree_path}\n"
        f"- **Branch**: {branch_name}\n"
        f"- **Planned Approach**:\n"
        f"  1. Isolate environment in worktree {branch_name}.\n"
        f"  2. Implement requested changes following modular anti-monolith guidelines.\n"
        f"  3. Verify unit tests and update CHANGELOG.md.\n"
        f"  4. Open Pull Request and submit for review.\n"
        f"- **Budget Guardrail**: Max 15 tool execution turns before pause & review.\n\n"
        f"---\n"
        f"*Posted automatically by Agent Manager Supervisor | Worktree: {worktree_path}*"
    )
    try:
        await post_issue_comment(repo, issue_number, comment_body)
        logger.info(f"Posted takeover comment to {repo}#{issue_number}")
    except Exception as e:
        logger.warning(f"Failed to post takeover comment to {repo}#{issue_number}: {e}")


async def sync_issue_board_status(repo: str, issue_number: int, status_key: str) -> None:
    try:
        from agent_manager.poller import LocalGitWatcher
        watcher = LocalGitWatcher()
        await watcher.update_issue_status(repo, issue_number, status_key)
        logger.info(f"Updated Project Board for {repo}#{issue_number} to '{status_key}'")
    except Exception as e:
        logger.warning(f"Failed to update board status for {repo}#{issue_number} to {status_key}: {e}")


def verify_changelog_update(cwd_dir: str, branch_name: str) -> bool:
    try:
        diff_output = subprocess.check_output(
            ["git", "diff", "--name-only", "main", branch_name],
            cwd=cwd_dir,
            text=True,
            stderr=subprocess.STDOUT
        )
        if "CHANGELOG.md" in diff_output:
            return True
        
        status_output = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=cwd_dir,
            text=True,
            stderr=subprocess.STDOUT
        )
        if "CHANGELOG.md" in status_output:
            return True
            
        return False
    except Exception as e:
        logger.warning(f"Error checking CHANGELOG.md git diff in {cwd_dir}: {e}")
        return False


def verify_worktree_quality_gate(cwd_dir: str, branch_name: str) -> Dict[str, Any]:
    """
    Enforces Section 5 (Anti-Monolith < 250 LOC) and Section 7 (Functions < 40 LOC)
    against all files modified in the active worktree before permitting PR review.
    """
    violations = []
    has_changelog = verify_changelog_update(cwd_dir, branch_name)
    if not has_changelog:
        violations.append("CHANGELOG.md has not been updated with release notes.")

    try:
        diff_files = subprocess.check_output(
            ["git", "diff", "--name-only", "main", branch_name],
            cwd=cwd_dir,
            text=True,
            stderr=subprocess.STDOUT
        ).splitlines()

        import ast
        for rel_file in diff_files:
            file_path = Path(cwd_dir) / rel_file
            if file_path.suffix == ".py" and file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                lines = content.splitlines()
                if len(lines) > 250:
                    violations.append(f"File '{rel_file}' has {len(lines)} LOC, exceeding the 250 LOC limit.")

                try:
                    tree = ast.parse(content, filename=str(file_path))
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            fn_len = getattr(node, "end_lineno", node.lineno) - node.lineno + 1
                            if fn_len > 40:
                                violations.append(f"Function '{node.name}' in '{rel_file}' has {fn_len} LOC, exceeding the 40 LOC limit.")
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Error running quality gate checks in {cwd_dir}: {e}")

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "changelog_updated": has_changelog
    }


def cleanup_merged_worktrees(repo_root: Optional[Path] = None, dry_run: bool = False) -> Dict[str, Any]:
    """Runs autonomous worktree pruning for merged or stale branches."""
    from agent_manager.services.worktree_cleaner import prune_stale_worktrees
    return prune_stale_worktrees(repo_root=repo_root, dry_run=dry_run)


