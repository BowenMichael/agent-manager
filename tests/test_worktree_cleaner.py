"""
Unit Tests for Autonomous Stale Worktree Pruner Service.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC).
"""

import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent_manager.services.worktree_cleaner import (
    parse_worktree_list,
    get_merged_branches,
    get_active_session_worktrees,
    prune_stale_worktrees
)
from agent_manager.runners.supervisor import cleanup_merged_worktrees


class TestWorktreeCleaner(unittest.TestCase):
    def test_parse_worktree_list(self):
        mock_raw = (
            "worktree /repo\nHEAD abc1234\nbranch refs/heads/main\n\n"
            "worktree /repo/.worktrees/issue-10\nHEAD def5678\nbranch refs/heads/feat/issue-10\n\n"
        )
        with patch("subprocess.check_output", return_value=mock_raw):
            result = parse_worktree_list(Path("/repo"))
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["branch"], "main")
            self.assertEqual(result[1]["path"], "/repo/.worktrees/issue-10")
            self.assertEqual(result[1]["branch"], "feat/issue-10")

    def test_get_merged_branches(self):
        mock_raw = "  main\n* feat/issue-10\n  feat/issue-12\n"
        with patch("subprocess.check_output", return_value=mock_raw):
            merged = get_merged_branches(Path("/repo"), base_branch="main")
            self.assertIn("main", merged)
            self.assertIn("feat/issue-10", merged)
            self.assertIn("feat/issue-12", merged)

    @patch("agent_manager.services.worktree_cleaner.is_process_alive")
    @patch("agent_manager.services.worktree_cleaner.load_sessions")
    def test_get_active_session_worktrees(self, mock_load, mock_alive):
        mock_sess1 = MagicMock(pid=1234, worktree_path="/repo/.worktrees/issue-1")
        mock_sess2 = MagicMock(pid=5678, worktree_path="/repo/.worktrees/issue-2")
        mock_sess3 = MagicMock(pid=None, worktree_path="/repo/.worktrees/issue-3")
        mock_load.return_value = {
            "s1": mock_sess1,
            "s2": mock_sess2,
            "s3": mock_sess3
        }
        mock_alive.side_effect = lambda pid: pid == 1234

        active = get_active_session_worktrees()
        self.assertIn(str(Path("/repo/.worktrees/issue-1").resolve()).lower(), active)
        self.assertNotIn(str(Path("/repo/.worktrees/issue-2").resolve()).lower(), active)

    @patch("agent_manager.services.worktree_cleaner.parse_worktree_list")
    @patch("agent_manager.services.worktree_cleaner.get_merged_branches")
    @patch("agent_manager.services.worktree_cleaner.get_active_session_worktrees")
    def test_prune_stale_worktrees_dry_run(self, mock_active, mock_merged, mock_list):
        mock_list.return_value = [
            {"path": "/repo", "branch": "main"},
            {"path": "/repo/.worktrees/issue-10", "branch": "feat/issue-10"},
            {"path": "/repo/.worktrees/issue-20", "branch": "feat/issue-20"},
            {"path": "/repo/.worktrees/issue-30", "branch": "feat/issue-30"},
        ]
        mock_merged.return_value = {"main", "feat/issue-10"}
        mock_active.return_value = {str(Path("/repo/.worktrees/issue-20").resolve()).lower()}

        report = prune_stale_worktrees(repo_root=Path("/repo"), dry_run=True)

        self.assertTrue(report["dry_run"])
        self.assertEqual(report["pruned_count"], 1)
        self.assertEqual(report["pruned"][0]["branch"], "feat/issue-10")

        # issue-20 was skipped because active agent running
        skipped_reasons = {s["path"]: s["reason"] for s in report["skipped"]}
        self.assertIn("Active agent process is running", skipped_reasons.get("/repo/.worktrees/issue-20", ""))
        # issue-30 was skipped because not merged
        self.assertIn("Not merged into main", skipped_reasons.get("/repo/.worktrees/issue-30", ""))

    @patch("agent_manager.services.worktree_cleaner.parse_worktree_list")
    @patch("agent_manager.services.worktree_cleaner.get_merged_branches")
    @patch("agent_manager.services.worktree_cleaner.get_active_session_worktrees")
    @patch("agent_manager.services.worktree_cleaner._prune_single_worktree")
    def test_prune_stale_worktrees_execution(self, mock_prune, mock_active, mock_merged, mock_list):
        mock_list.return_value = [
            {"path": "/repo/.worktrees/issue-10", "branch": "feat/issue-10"}
        ]
        mock_merged.return_value = {"feat/issue-10"}
        mock_active.return_value = set()
        mock_prune.return_value = True

        report = cleanup_merged_worktrees(repo_root=Path("/repo"), dry_run=False)

        self.assertEqual(report["pruned_count"], 1)
        self.assertEqual(report["pruned"][0]["branch"], "feat/issue-10")
        mock_prune.assert_called_once()


if __name__ == "__main__":
    unittest.main()
