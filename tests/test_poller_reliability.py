"""
Unit tests for Poller Reliability, GraphQL Retry Backoff, and Sync Broadcasting.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from agent_manager.poller.github_client import (
    GitHubBoardClient,
    execute_graphql_with_retry
)
from agent_manager.poller.synchronizer import broadcast_board_sync
from agent_manager.poller.watcher import LocalGitWatcher


class TestPollerReliability(unittest.IsolatedAsyncioTestCase):
    """Test suite for poller retry backoff, field resolution, and WebSocket broadcasting."""

    @patch("httpx.AsyncClient.post")
    async def test_execute_graphql_success(self, mock_post):
        """Verify GraphQL client returns JSON data on 200 OK."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": {"test": "value"}}
        mock_post.return_value = mock_resp

        result = await execute_graphql_with_retry("query { test }", {})
        self.assertIsNotNone(result)
        self.assertEqual(result["data"]["test"], "value")

    @patch("httpx.AsyncClient.post")
    async def test_execute_graphql_retry_on_rate_limit(self, mock_post):
        """Verify client retries upon receiving 429 and succeeds on next attempt."""
        fail_resp = MagicMock()
        fail_resp.status_code = 429
        fail_resp.headers = {"retry-after": "0.01"}

        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.json.return_value = {"data": {"recovered": True}}

        mock_post.side_effect = [fail_resp, success_resp]

        result = await execute_graphql_with_retry("query { test }", {}, max_retries=2)
        self.assertIsNotNone(result)
        self.assertTrue(result["data"]["recovered"])
        self.assertEqual(mock_post.call_count, 2)

    def test_extract_status_fields(self):
        """Verify status option IDs are correctly parsed from GraphQL node list."""
        client = GitHubBoardClient()
        mock_nodes = [
            {
                "name": "Status",
                "id": "field_status_123",
                "options": [
                    {"id": "opt_ready", "name": "📋 Ready for Agent"},
                    {"id": "opt_progress", "name": "⚡ In Progress"},
                    {"id": "opt_review", "name": "🔍 In Review"},
                    {"id": "opt_done", "name": "✅ Done"}
                ]
            }
        ]
        info = client._extract_status_field(mock_nodes)
        self.assertIsNotNone(info)
        self.assertEqual(info["field_id"], "field_status_123")
        self.assertEqual(info["options"]["ready"], "opt_ready")
        self.assertEqual(info["options"]["in_progress"], "opt_progress")

    async def test_broadcast_board_sync(self):
        """Verify WebSocket sync event is formatted and emitted."""
        watcher = MagicMock()
        watcher.runner.broadcast = AsyncMock()

        await broadcast_board_sync(watcher, issue_num=127, repo="BowenMichael/agent-manager", status_key="in_progress")
        watcher.runner.broadcast.assert_called_once()
        payload = watcher.runner.broadcast.call_args[0][0]
        self.assertEqual(payload["type"], "board_status_sync")
        self.assertEqual(payload["data"]["issue_number"], 127)
        self.assertEqual(payload["data"]["status"], "in_progress")


if __name__ == "__main__":
    unittest.main()
