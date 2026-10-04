"""
Regression tests for GitHub inbound webhooks, specifically verifying that
agent self-comments across all formats are properly ignored.
"""
import unittest
import asyncio
from unittest.mock import patch, AsyncMock

from agent_manager.webhooks import process_github_event
from agent_manager.models import AgentSessionInfo, AgentStatus
from agent_manager.runner import AgentRunnerManager
from agent_manager.formatters.comments import (
    format_agent_comment,
    BADGE_AGENT_UPDATE,
    BADGE_AGENT_TAKEOVER,
    FOOTER_SIGNATURE
)


class TestWebhookAgentCommentFiltering(unittest.TestCase):
    def setUp(self):
        self.runner = AgentRunnerManager()
        self.session_id = "test-webhook-session-7"
        self.session = AgentSessionInfo(
            session_id=self.session_id,
            title="Issue 7 Webhook Test",
            repo="BowenMichael/agent-manager",
            issue_number=7,
            git_branch="feat/issue-7",
            status=AgentStatus.IN_REVIEW,
            seen_comment_ids=[]
        )
        self.runner.sessions[self.session_id] = self.session

    def tearDown(self):
        if self.session_id in self.runner.sessions:
            del self.runner.sessions[self.session_id]

    async def _post_comment_event(self, comment_body: str, comment_id: int = 12345):
        payload = {
            "action": "created",
            "issue": {"number": 7},
            "repository": {"full_name": "BowenMichael/agent-manager"},
            "comment": {
                "id": comment_id,
                "body": comment_body,
                "user": {"login": "test-user"}
            }
        }
        return await process_github_event("issue_comment", payload)

    @patch("agent_manager.webhooks.LocalGitWatcher.update_issue_status", new_callable=AsyncMock)
    @patch("agent_manager.runner.AgentRunnerManager.add_context", new_callable=AsyncMock)
    def test_human_comment_triggers_context_injection(self, mock_add_context, mock_update_status):
        res = asyncio.run(
            self._post_comment_event("Can you check if the styles align with the UI mockup?")
        )
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["action"], "context_injected")
        mock_add_context.assert_called_once()

    def test_agent_update_comment_ignored(self):
        agent_comment = format_agent_comment(
            body="Completed the first pass of changes.",
            header=BADGE_AGENT_UPDATE,
            session_id=self.session_id,
            git_branch="feat/issue-7"
        )
        res = asyncio.run(self._post_comment_event(agent_comment))
        self.assertEqual(res["status"], "ignored")
        self.assertEqual(res["reason"], "agent_self_comment")

    def test_agent_takeover_comment_ignored(self):
        takeover_comment = (
            f"{BADGE_AGENT_TAKEOVER}\n\n"
            f"- **Worktree**: `.worktrees/issue-7`\n"
            f"- **Branch**: `feat/issue-7`\n\n"
            f"---\n*{FOOTER_SIGNATURE}*"
        )
        res = asyncio.run(self._post_comment_event(takeover_comment))
        self.assertEqual(res["status"], "ignored")
        self.assertEqual(res["reason"], "agent_self_comment")

    def test_circuit_breaker_pause_comment_ignored(self):
        pause_comment = (
            "⚠️ **Task Paused: Circuit Breaker Triggered**\n\n"
            "### 🛑 Repetitive Tool Loop Detected\n- Tool: `view_file`\n\n"
            f"---\n*{FOOTER_SIGNATURE} | Session: `{self.session_id}`*"
        )
        res = asyncio.run(self._post_comment_event(pause_comment))
        self.assertEqual(res["status"], "ignored")
        self.assertEqual(res["reason"], "agent_self_comment")

    def test_turn_budget_pause_comment_ignored(self):
        turn_budget_comment = (
            "⚠️ **Task Paused: Token / Complexity Budget Threshold Reached**\n\n"
            "### 📊 Task Insights\n- Turns Completed: 15 / 15\n\n"
            f"---\n*{FOOTER_SIGNATURE} | Session: `{self.session_id}`*"
        )
        res = asyncio.run(self._post_comment_event(turn_budget_comment))
        self.assertEqual(res["status"], "ignored")
        self.assertEqual(res["reason"], "agent_self_comment")


if __name__ == "__main__":
    unittest.main()
