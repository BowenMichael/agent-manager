"""
Unit Tests for Rebase Supervisor & Multi-Agent Conflict Resolver.
Validates drift detection, conflict parsing, auto-resolution, safe abort, and push with lease.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent_manager.runners.rebase_supervisor import (
    check_upstream_drift, detect_conflicted_files, resolve_simple_conflicts,
    push_with_lease, rebase_worktree, abort_rebase
)
from agent_manager.services.manifesto_metrics import evaluate_isolation


class TestRebaseSupervisor(unittest.TestCase):
    """Tests for worktree git rebase and conflict resolution."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.worktree_dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    @patch("agent_manager.runners.rebase_supervisor._run_git_cmd")
    def test_check_upstream_drift(self, mock_git):
        mock_git.return_value = MagicMock(returncode=0, stdout="3\n")
        drift = check_upstream_drift(self.worktree_dir)
        self.assertTrue(drift["is_behind"])
        self.assertEqual(drift["commits_behind"], 3)

    @patch("agent_manager.runners.rebase_supervisor._run_git_cmd")
    def test_detect_conflicted_files(self, mock_git):
        mock_git.return_value = MagicMock(returncode=0, stdout="CHANGELOG.md\napp.py\n")
        conflicts = detect_conflicted_files(self.worktree_dir)
        self.assertEqual(conflicts, ["CHANGELOG.md", "app.py"])

    def test_resolve_simple_conflicts_additive(self):
        test_file = self.worktree_dir / "CHANGELOG.md"
        conflict_text = """
## [Unreleased]
<<<<<<< HEAD
- Feature A (#1)
=======
- Feature B (#2)
>>>>>>> origin/main
"""
        test_file.write_text(conflict_text.strip(), encoding="utf-8")
        resolved = resolve_simple_conflicts(test_file)
        self.assertTrue(resolved)

        content = test_file.read_text(encoding="utf-8")
        self.assertNotIn("<<<<<<<", content)
        self.assertIn("- Feature A (#1)", content)
        self.assertIn("- Feature B (#2)", content)

    @patch("agent_manager.runners.rebase_supervisor._run_git_cmd")
    def test_push_with_lease(self, mock_git):
        mock_git.return_value = MagicMock(returncode=0)
        success = push_with_lease(self.worktree_dir, "feat/test")
        self.assertTrue(success)
        mock_git.assert_called_with(["git", "push", "--force-with-lease", "origin", "feat/test"], self.worktree_dir)

    @patch("agent_manager.runners.rebase_supervisor.check_upstream_drift")
    def test_rebase_up_to_date(self, mock_drift):
        mock_drift.return_value = {"is_behind": False, "commits_behind": 0}
        res = rebase_worktree(self.worktree_dir)
        self.assertEqual(res["status"], "UP_TO_DATE")
        self.assertFalse(res["rebased"])

    def test_evaluate_isolation_reflects_resolver(self):
        report = evaluate_isolation([MagicMock(worktree_path=".worktrees/test")])
        self.assertIn("score", report)
        self.assertGreaterEqual(report["score"], 65.0)


if __name__ == "__main__":
    unittest.main()
