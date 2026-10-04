import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from agent_manager.models import AgentSessionInfo, AgentStatus, ConversationMessage, MessageRole
from agent_manager.services.telemetry_service import (
    compute_tool_frequencies,
    generate_optimization_reports
)
from agent_manager.server import app


class TestTelemetryService(unittest.TestCase):
    def test_compute_tool_frequencies(self):
        messages = [
            ConversationMessage(id="1", role=MessageRole.USER, content="Hello"),
            ConversationMessage(id="2", role=MessageRole.TOOL_CALL, content="", tool_name="view_file"),
            ConversationMessage(id="3", role=MessageRole.TOOL_CALL, content="", tool_name="view_file"),
            ConversationMessage(id="4", role=MessageRole.TOOL_CALL, content="", tool_name="run_command"),
        ]
        freq = compute_tool_frequencies(messages)
        self.assertEqual(freq.get("view_file"), 2)
        self.assertEqual(freq.get("run_command"), 1)

    @patch("agent_manager.services.telemetry_service.load_sessions")
    def test_generate_optimization_reports_empty(self, mock_load):
        mock_load.return_value = {}
        report = generate_optimization_reports()
        self.assertEqual(report["summary"]["total_sessions"], 0)
        self.assertEqual(len(report["recommendations"]), 0)

    @patch("agent_manager.services.telemetry_service.load_sessions")
    def test_generate_optimization_reports_with_sessions(self, mock_load):
        s1 = AgentSessionInfo(
            session_id="s1",
            repo="BowenMichael/agent-manager",
            issue_number=65,
            title="Telemetry Page",
            status=AgentStatus.COMPLETED,
            turn_count=6,
            total_tokens=25000,
            duration_seconds=120.0,
            messages=[
                ConversationMessage(id="m1", role=MessageRole.TOOL_CALL, content="", tool_name="view_file"),
                ConversationMessage(id="m2", role=MessageRole.TOOL_CALL, content="", tool_name="run_command")
            ]
        )
        s2 = AgentSessionInfo(
            session_id="s2",
            repo="BowenMichael/f1-frontend",
            issue_number=10,
            title="Bugfix issue",
            status=AgentStatus.FAILED,
            turn_count=15,
            total_tokens=140000,
            duration_seconds=300.0,
            circuit_breaker_triggered=True,
            consecutive_duplicate_tool_count=3,
            consecutive_view_file_count=8,
            messages=[
                ConversationMessage(id="m3", role=MessageRole.TOOL_CALL, content="", tool_name="view_file")
            ]
        )
        mock_load.return_value = {"s1": s1, "s2": s2}

        report = generate_optimization_reports()
        summary = report["summary"]
        self.assertEqual(summary["total_sessions"], 2)
        self.assertEqual(summary["completed_sessions"], 1)
        self.assertEqual(summary["failed_sessions"], 1)
        self.assertEqual(summary["success_rate_percent"], 50.0)
        self.assertEqual(summary["avg_duration_seconds"], 210.0)
        self.assertEqual(summary["avg_turn_count"], 10.5)

        # Check tool frequency roll-up
        self.assertEqual(report["tool_usage"]["view_file"], 2)
        self.assertEqual(report["tool_usage"]["run_command"], 1)

        # Check optimization recommendations
        recs = report["recommendations"]
        types = [r["type"] for r in recs]
        self.assertIn("circuit_breaker", types)
        self.assertIn("duplicate_tool_loop", types)
        self.assertIn("excessive_reads", types)
        self.assertIn("high_turn_count", types)

    @patch("agent_manager.services.telemetry_service.load_sessions")
    def test_api_telemetry_reports_endpoint(self, mock_load):
        mock_load.return_value = {}
        client = TestClient(app)
        response = client.get("/api/telemetry/reports")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("summary", data)
        self.assertIn("tool_usage", data)
        self.assertIn("recommendations", data)
        self.assertIn("session_performances", data)
