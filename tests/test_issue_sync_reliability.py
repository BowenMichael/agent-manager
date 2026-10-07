"""
Unit & Integration Tests for Issue Synchronization & State Reconciliation.
Verifies debounce timing, acceptance criteria parsing, and WebSocket broadcast events.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import asyncio
import time
import unittest
from unittest.mock import patch, AsyncMock, MagicMock

from agent_manager.poller.reconciler import (
    IssueSyncReconciler,
    parse_acceptance_criteria,
    is_valid_transition
)
from agent_manager.poller.watcher import LocalGitWatcher


class TestAcceptanceCriteriaParser(unittest.TestCase):
    """Verifies markdown checkbox parsing for issue bodies."""

    def test_empty_or_none_body(self):
        """Empty or None body returns 1.0 ratio with 0 checkboxes."""
        self.assertEqual(parse_acceptance_criteria(None), {"total": 0, "completed": 0, "ratio": 1.0})
        self.assertEqual(parse_acceptance_criteria(""), {"total": 0, "completed": 0, "ratio": 1.0})

    def test_parsed_checkboxes_partial(self):
        """Mixed checked and unchecked markdown items are parsed correctly."""
        body = "### Criteria\n- [x] Item 1\n- [ ] Item 2\n- [X] Item 3\n- [ ] Item 4"
        stats = parse_acceptance_criteria(body)
        self.assertEqual(stats["total"], 4)
        self.assertEqual(stats["completed"], 2)
        self.assertEqual(stats["ratio"], 0.5)

    def test_parsed_checkboxes_complete(self):
        """All checked items yield a 1.0 ratio."""
        body = "- [x] Done 1\n- [x] Done 2"
        stats = parse_acceptance_criteria(body)
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["completed"], 2)
        self.assertEqual(stats["ratio"], 1.0)


class TestStateTransitions(unittest.TestCase):
    """Verifies state transition validation logic."""

    def test_valid_transitions(self):
        """Valid transitions follow standard development lifecycle."""
        self.assertTrue(is_valid_transition("ready", "in_progress"))
        self.assertTrue(is_valid_transition("in_progress", "in_review"))
        self.assertTrue(is_valid_transition("in_review", "done"))
        self.assertTrue(is_valid_transition("done", "ready"))

    def test_invalid_transitions(self):
        """Direct illegal jumps across state boundaries are rejected."""
        self.assertFalse(is_valid_transition("backlog", "done"))
        self.assertFalse(is_valid_transition("backlog", "in_review"))


class TestIssueSyncReconciler(unittest.IsolatedAsyncioTestCase):
    """Verifies debounce logic and broadcast payload generation."""

    async def test_debounce_blocks_rapid_duplicate_syncs(self):
        """Debounce window prevents rapid-fire duplicate sync calls."""
        reconciler = IssueSyncReconciler(debounce_window_sec=0.5)
        repo = "BowenMichael/agent-manager"
        issue_num = 142

        # First call succeeds
        should_first = await reconciler.should_sync(repo, issue_num)
        self.assertTrue(should_first)
        await reconciler.mark_sync_complete(repo, issue_num)

        # Immediate second call is debounced
        should_second = await reconciler.should_sync(repo, issue_num)
        self.assertFalse(should_second)

        # Wait for debounce window to elapse
        await asyncio.sleep(0.55)
        should_third = await reconciler.should_sync(repo, issue_num)
        self.assertTrue(should_third)
        await reconciler.mark_sync_complete(repo, issue_num)

    async def test_reconcile_event_emits_broadcast(self):
        """Reconciliation triggers WebSocket broadcast with full metadata."""
        reconciler = IssueSyncReconciler(debounce_window_sec=0.1)
        watcher = MagicMock()
        watcher.update_issue_status = AsyncMock(return_value=True)
        watcher.runner.broadcast = AsyncMock()

        res = await reconciler.reconcile_issue_event(
            watcher,
            repo="BowenMichael/agent-manager",
            issue_number=142,
            target_status="in_progress",
            source="test_runner",
            body="### Criteria\n- [x] Step 1\n- [ ] Step 2"
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["data"]["status"], "in_progress")
        self.assertEqual(res["data"]["criteria"]["completed"], 1)
        watcher.runner.broadcast.assert_called_once()
        broadcast_data = watcher.runner.broadcast.call_args[0][0]
        self.assertEqual(broadcast_data["type"], "board_status_sync")
        self.assertEqual(broadcast_data["data"]["issue_number"], 142)


class TestLocalGitWatcherReconcile(unittest.IsolatedAsyncioTestCase):
    """Verifies LocalGitWatcher integration with reconciler."""

    def setUp(self):
        LocalGitWatcher._instance = None

    def tearDown(self):
        LocalGitWatcher._instance = None

    async def test_watcher_reconcile_event_flow(self):
        """Watcher delegates to reconciler and updates issue status."""
        watcher = LocalGitWatcher()
        with patch.object(watcher, "update_issue_status", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = True
            watcher.runner.broadcast = AsyncMock()

            res = await watcher.reconcile_event(
                repo="BowenMichael/agent-manager",
                issue_number=142,
                status_key="in_progress",
                source="poller"
            )
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["data"]["status"], "in_progress")
            mock_update.assert_called_once_with("BowenMichael/agent-manager", 142, "in_progress")


if __name__ == "__main__":
    unittest.main()

