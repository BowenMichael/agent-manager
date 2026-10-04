"""
Unit tests for the Pre-Execution Agent Interpretation phase (Issue #72).
Verifies:
1. is_sparse_issue detection on title-only, empty, and template-only issues.
2. Formatted BADGE_AGENT_INTERPRETATION comment structure.
3. Pre-execution interpretation generation, GitHub comment posting, and Project Board transition.
4. Non-sparse issues bypass the interpretation generation and proceed directly to '⚡ In Progress'.
"""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from agent_manager.services.issue_evaluator import is_sparse_issue
from agent_manager.formatters.comments import (
    BADGE_AGENT_INTERPRETATION,
    format_agent_comment,
    FOOTER_SIGNATURE,
)
from agent_manager.models import SpawnRequest, AgentSessionInfo, AgentStatus
from agent_manager.services.interpretation import (
    build_interpretation_prompt,
    generate_and_post_interpretation,
    run_interpretation_and_start,
)


class TestAgentInterpretation(unittest.TestCase):
    def test_is_sparse_issue_detection(self):
        # Empty or None
        self.assertTrue(is_sparse_issue(None))
        self.assertTrue(is_sparse_issue(""))
        self.assertTrue(is_sparse_issue("   "))

        # Template boilerplate only
        template_body = """
### 🎯 Objective
<!-- Describe objective -->

### 📋 Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

### 📸 Visual Verification Required
- [ ] Screenshot or UI demonstration (if applicable)

### ℹ️ Context & Notes
<!-- Relevant architectural files -->
"""
        self.assertTrue(is_sparse_issue(template_body))

        # Title-only or very short description
        self.assertTrue(is_sparse_issue("fix bug in navbar"))
        self.assertTrue(is_sparse_issue("Short summary."))

        # Non-sparse, rich descriptions
        detailed_body = """
### 🎯 Objective
Refactor the authentication middleware to use Redis token revocation checks on every incoming request.

### 📋 Acceptance Criteria
- [ ] Ensure Redis client handles connection timeouts gracefully with 500ms fallback.
- [ ] Add rate-limiting unit tests covering 429 status code returns.
- [ ] Verify that invalid tokens return HTTP 401 with structured JSON errors.
"""
        self.assertFalse(is_sparse_issue(detailed_body))

    def test_interpretation_prompt_generation(self):
        prompt = build_interpretation_prompt("Fix Auth Token Expiry", "", 72)
        self.assertIn("GitHub Issue #72", prompt)
        self.assertIn("Fix Auth Token Expiry", prompt)
        self.assertIn("Agent Interpretation", prompt)
        self.assertIn("Proposed Acceptance Criteria", prompt)

    def test_badge_and_comment_formatting(self):
        raw_interpretation = (
            "### 🤖 Agent Interpretation & Scope Breakdown\n"
            "This task implements the Redis revocation middleware with fallback handling."
        )
        formatted = format_agent_comment(
            body=raw_interpretation,
            header=BADGE_AGENT_INTERPRETATION,
            session_id="issue-72-test",
            git_branch="feat/issue-72",
            worktree_path=".worktrees/issue-72"
        )
        self.assertIn(BADGE_AGENT_INTERPRETATION, formatted)
        self.assertIn(FOOTER_SIGNATURE, formatted)
        self.assertIn("Session: `issue-72-test`", formatted)
        self.assertIn("Branch: `feat/issue-72`", formatted)
        self.assertIn("Worktree: `.worktrees/issue-72`", formatted)

    def test_run_interpretation_and_start_for_sparse_issue(self):
        async def run_async():
            mock_runner = MagicMock()
            mock_runner.broadcast = AsyncMock()
            mock_runner._save = MagicMock()
            mock_runner._run_cli_turn = AsyncMock(
                return_value="### 1. Inferred Scope\nImplement pre-execution interpretation pipeline."
            )
            mock_runner._append_message = AsyncMock()
            mock_runner._run_agent_loop = AsyncMock()
            mock_runner._tasks = {}

            mock_watcher = MagicMock()
            mock_watcher.runner = mock_runner
            mock_watcher.update_item_status = AsyncMock()

            session = AgentSessionInfo(
                session_id="issue-72-test",
                repo="BowenMichael/agent-manager",
                issue_number=72,
                title="Agent planning before in progress",
                status=AgentStatus.INITIALIZING,
                worktree_path=".worktrees/issue-72",
                git_branch="feat/issue-72"
            )

            spawn_req = SpawnRequest(
                repo="BowenMichael/agent-manager",
                issue_number=72,
                title="Agent planning before in progress",
                prompt="Initial prompt"
            )

            with patch("agent_manager.services.interpretation.post_issue_comment", new_callable=AsyncMock) as mock_post:
                await run_interpretation_and_start(
                    watcher=mock_watcher,
                    item_id="item-123",
                    issue_key="BowenMichael/agent-manager#72",
                    spawn_req=spawn_req,
                    session=session,
                    raw_body=""  # Sparse / title-only
                )

                # CLI turn should be called to generate interpretation
                mock_runner._run_cli_turn.assert_awaited_once()

                # Comment posted to GitHub
                mock_post.assert_awaited_once()
                args, _ = mock_post.call_args
                self.assertEqual(args[0], "BowenMichael/agent-manager")
                self.assertEqual(args[1], 72)
                self.assertIn(BADGE_AGENT_INTERPRETATION, args[2])

                # Status transitioned to in_progress AFTER interpretation
                mock_watcher.update_item_status.assert_awaited_once_with("item-123", "in_progress")

                # Main agent loop started
                self.assertIn(session.session_id, mock_runner._tasks)

        asyncio.run(run_async())

    def test_run_interpretation_and_start_for_non_sparse_issue(self):
        async def run_async():
            mock_runner = MagicMock()
            mock_runner.broadcast = AsyncMock()
            mock_runner._save = MagicMock()
            mock_runner._run_cli_turn = AsyncMock()
            mock_runner._run_agent_loop = AsyncMock()
            mock_runner._tasks = {}

            mock_watcher = MagicMock()
            mock_watcher.runner = mock_runner
            mock_watcher.update_item_status = AsyncMock()

            session = AgentSessionInfo(
                session_id="issue-80-test",
                repo="BowenMichael/agent-manager",
                issue_number=80,
                title="Rich detailed task",
                status=AgentStatus.INITIALIZING,
                worktree_path=".worktrees/issue-80",
                git_branch="feat/issue-80"
            )

            spawn_req = SpawnRequest(
                repo="BowenMichael/agent-manager",
                issue_number=80,
                title="Rich detailed task",
                prompt="Initial prompt"
            )

            rich_body = """
### 🎯 Objective
Complete and rich description that provides all details needed for execution.

### 📋 Acceptance Criteria
- [ ] Criterion 1: Thorough validation check
- [ ] Criterion 2: Comprehensive test suite passes
"""

            with patch("agent_manager.services.interpretation.post_issue_comment", new_callable=AsyncMock) as mock_post:
                await run_interpretation_and_start(
                    watcher=mock_watcher,
                    item_id="item-456",
                    issue_key="BowenMichael/agent-manager#80",
                    spawn_req=spawn_req,
                    session=session,
                    raw_body=rich_body
                )

                # Non-sparse should NOT trigger CLI turn or extra comment
                mock_runner._run_cli_turn.assert_not_called()
                mock_post.assert_not_called()

                # Status should still transition to in_progress directly
                mock_watcher.update_item_status.assert_awaited_once_with("item-456", "in_progress")

                # Main loop launched
                self.assertIn(session.session_id, mock_runner._tasks)

        asyncio.run(run_async())


if __name__ == "__main__":
    unittest.main()
