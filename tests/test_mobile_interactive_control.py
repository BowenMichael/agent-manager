"""
Unit & Integration Tests for Expo Mobile Interactive Context Injection & Control Actions.
Verifies mobile REST control client, context injection routes, and Anti-Monolith constraints.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path

from fastapi.testclient import TestClient
from agent_manager.server import app
from agent_manager.models import AgentSessionInfo, AgentStatus


class TestMobileInteractiveControl(unittest.TestCase):
    """Test suite for Expo mobile interactive control endpoints and source validation."""

    def setUp(self):
        self.client = TestClient(app)
        self.repo_root = Path(__file__).resolve().parent.parent

    def test_mobile_source_anti_monolith_limits(self):
        """Verify mobile control components adhere strictly to < 250 LOC."""
        files_to_check = [
            self.repo_root / "apps" / "mobile" / "components" / "SessionControlBar.tsx",
            self.repo_root / "apps" / "mobile" / "services" / "agentApi.ts",
            self.repo_root / "apps" / "mobile" / "app" / "session" / "[id].tsx",
        ]
        for f in files_to_check:
            self.assertTrue(f.exists(), f"File {f.name} does not exist")
            lines = f.read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(len(lines), 250, f"{f.name} exceeds 250 LOC ({len(lines)} lines)")

    @patch("agent_manager.api.routes.agents.runner")
    def test_context_injection_endpoint(self, mock_runner):
        """Verify POST /api/agents/{id}/context accepts mobile prompts."""
        mock_runner.add_context = AsyncMock(return_value=True)

        res = self.client.post("/api/agents/session-mob-1/context", json={"prompt": "Focus on mobile styles"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "ok")

    @patch("agent_manager.api.routes.agents.runner")
    def test_pause_and_resume_control_actions(self, mock_runner):
        """Verify POST /api/agents/{id}/pause and resume endpoints."""
        mock_runner.interrupt_agent = AsyncMock(return_value=True)
        mock_runner.resume_agent = AsyncMock(return_value=True)

        res_pause = self.client.post("/api/agents/session-mob-1/pause")
        self.assertEqual(res_pause.status_code, 200)

        res_resume = self.client.post("/api/agents/session-mob-1/resume")
        self.assertEqual(res_resume.status_code, 200)

    @patch("agent_manager.api.routes.agents.runner")
    def test_stop_control_action(self, mock_runner):
        """Verify POST /api/agents/{id}/stop endpoint."""
        mock_runner.stop_agent = AsyncMock(return_value=True)

        res = self.client.post("/api/agents/session-mob-1/stop")
        self.assertEqual(res.status_code, 200)

    @patch("agent_manager.api.routes.agents.runner")
    def test_update_parameters_endpoint(self, mock_runner):
        """Verify POST /api/agents/{id}/parameters updates model and effort."""
        mock_session = MagicMock()
        mock_session.model_dump.return_value = {"model": "gemini-2.5-pro", "effort": "high"}
        mock_runner.get_session.return_value = mock_session
        mock_runner._save = MagicMock()
        mock_runner.broadcast = AsyncMock()

        res = self.client.post("/api/agents/session-mob-1/parameters", json={"model": "gemini-2.5-pro", "effort": "high"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(mock_session.model, "gemini-2.5-pro")
        self.assertEqual(mock_session.effort, "high")



if __name__ == "__main__":
    unittest.main()
