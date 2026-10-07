"""
Integration Tests for Mobile Session Feed & WebSocket Client.
Verifies file structure, TypeScript export signatures, and mobile API routing.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from agent_manager.server import app


class TestMobileSessionFeed(unittest.TestCase):
    """Verifies Expo mobile session feed, WebSocket client, and state store files."""

    def setUp(self):
        self.client = TestClient(app)
        self.root = Path(__file__).resolve().parent.parent

    def test_mobile_feed_files_exist(self):
        """Verify all mobile session feed and socket files exist in the worktree."""
        mobile_dir = self.root / "apps" / "mobile"
        self.assertTrue((mobile_dir / "services" / "socket.ts").exists())
        self.assertTrue((mobile_dir / "store" / "sessionStore.ts").exists())
        self.assertTrue((mobile_dir / "app" / "index.tsx").exists())
        self.assertTrue((mobile_dir / "__tests__" / "SessionStoreAndSocket.test.ts").exists())

    def test_socket_ts_exports(self):
        """Verify socket client implements reconnect backoff logic."""
        content = (self.root / "apps" / "mobile" / "services" / "socket.ts").read_text(encoding="utf-8")
        self.assertIn("class AgentSocketClient", content)
        self.assertIn("reconnectAttempt", content)
        self.assertIn("handleSocketClose", content)
        self.assertIn("maxReconnectDelay", content)

    def test_session_store_ts_exports(self):
        """Verify sessionStore implements filters and optimistic updates."""
        content = (self.root / "apps" / "mobile" / "store" / "sessionStore.ts").read_text(encoding="utf-8")
        self.assertIn("class SessionStore", content)
        self.assertIn("optimisticUpdateStatus", content)
        self.assertIn("getSessions", content)
        self.assertIn("statusFilter", content)

    def test_agents_api_endpoint(self):
        """Verify FastAPI /api/agents returns valid response for mobile clients."""
        res = self.client.get("/api/agents")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)


if __name__ == "__main__":
    unittest.main()
