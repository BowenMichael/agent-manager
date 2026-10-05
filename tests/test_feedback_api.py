"""
Unit & Integration Tests for Universal Feedback Flywheel API.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC).
"""

import unittest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from agent_manager.server import app
from agent_manager.services.feedback_service import (
    FeedbackSubmissionRequest,
    resolve_target_repo,
    format_feedback_body,
    ingest_feedback
)


class TestFeedbackFlywheelAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_resolve_target_repo(self):
        self.assertEqual(resolve_target_repo("fitelo"), "BowenMichael/fit-elo")
        self.assertEqual(resolve_target_repo("f1-frontend"), "BowenMichael/f1-frontend")
        self.assertEqual(resolve_target_repo("unknown-app", "Custom/repo"), "Custom/repo")

    def test_format_feedback_body(self):
        req = FeedbackSubmissionRequest(
            app_name="fitelo",
            feedback_type="bug",
            title="Timer reset on reload",
            description="The rest timer drops to 0 when refreshing the browser page.",
            route="/workout/active",
            user_agent="Mozilla/5.0",
            viewport={"width": 390, "height": 844},
            console_logs=[{"level": "error", "message": "IndexedDB quota exceeded"}]
        )
        body = format_feedback_body(req, "BowenMichael/fit-elo")
        self.assertIn("The rest timer drops to 0", body)
        self.assertIn("IndexedDB quota exceeded", body)
        self.assertIn("390x844", body)
        self.assertIn("Acceptance Criteria", body)

    @patch("agent_manager.services.feedback_service.create_github_issue")
    def test_ingest_feedback_success(self, mock_create):
        mock_create.return_value = {
            "number": 105,
            "html_url": "https://github.com/BowenMichael/fit-elo/issues/105"
        }
        req = FeedbackSubmissionRequest(
            app_name="fitelo",
            title="Add dark mode toggle",
            description="Dark mode support for night workouts",
            feedback_type="feature",
            auto_assign=False
        )
        import asyncio
        res = asyncio.run(ingest_feedback(req))
        self.assertTrue(res["success"])
        self.assertEqual(res["issue_number"], 105)
        self.assertEqual(res["status"], "Ready for Agent")

    @patch("agent_manager.services.feedback_service.create_github_issue")
    def test_feedback_submit_endpoint(self, mock_create):
        mock_create.return_value = {
            "number": 106,
            "html_url": "https://github.com/BowenMichael/agent-manager/issues/106"
        }
        payload = {
            "app_name": "agent-manager",
            "feedback_type": "bug",
            "title": "WebSocket reconnect delay",
            "description": "WebSocket takes 10s to reconnect after waking laptop from sleep.",
            "route": "/sessions/active",
            "auto_assign": False
        }
        res = self.client.post("/api/feedback/submit", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["issue_number"], 106)

    def test_feedback_submit_validation_error(self):
        # Missing required fields
        res = self.client.post("/api/feedback/submit", json={"app_name": "fitelo"})
        self.assertEqual(res.status_code, 422)


if __name__ == "__main__":
    unittest.main()
