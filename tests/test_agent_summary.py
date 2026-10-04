import unittest
from fastapi.testclient import TestClient
from agent_manager.server import app, runner
from agent_manager.models import AgentSessionInfo, AgentStatus, WorkflowStage

class TestAgentSummaryOverview(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.original_sessions = runner.sessions.copy()
        runner.sessions = {}

    def tearDown(self):
        runner.sessions = self.original_sessions

    def test_agent_summary_data_contract_serialization(self):
        session_info = AgentSessionInfo(
            session_id="test-session-summary",
            repo="BowenMichael/agent-manager",
            issue_number=32,
            title="Add automatically refreshing summary",
            status=AgentStatus.RUNNING,
            current_activity="Executing tool grep_search",
            is_stalled=False,
            workflow_stage=WorkflowStage.IMPLEMENTING,
            turn_count=5,
            max_turns=15,
            quota_percent=33.3,
            duration_seconds=124.5,
            token_count=12000,
            total_tokens=12000
        )
        runner.sessions["test-session-summary"] = session_info

        res = self.client.get("/api/agents")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 1)

        item = data[0]
        self.assertEqual(item["session_id"], "test-session-summary")
        self.assertEqual(item["repo"], "BowenMichael/agent-manager")
        self.assertEqual(item["issue_number"], 32)
        self.assertEqual(item["title"], "Add automatically refreshing summary")
        self.assertEqual(item["status"], "RUNNING")
        self.assertEqual(item["current_activity"], "Executing tool grep_search")
        self.assertFalse(item["is_stalled"])
        self.assertEqual(item["workflow_stage"], "IMPLEMENTING")
        self.assertEqual(item["turn_count"], 5)
        self.assertEqual(item["max_turns"], 15)
        self.assertEqual(item["quota_percent"], 33.3)
        self.assertEqual(item["duration_seconds"], 124.5)
        self.assertEqual(item["total_tokens"], 12000)

    def test_agent_summary_stalled_and_circuit_breaker(self):
        session_info = AgentSessionInfo(
            session_id="test-session-stalled",
            repo="BowenMichael/agent-manager",
            issue_number=33,
            title="Stalled Agent Test",
            status=AgentStatus.PAUSED,
            current_activity="⚠️ Paused by circuit breaker: duplicate tool call",
            is_stalled=True,
            circuit_breaker_triggered=True,
            workflow_stage=WorkflowStage.DIRECT,
            turn_count=15,
            max_turns=15,
            quota_percent=100.0,
            duration_seconds=300.0
        )
        runner.sessions["test-session-stalled"] = session_info

        res = self.client.get("/api/agents")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 1)

        item = data[0]
        self.assertTrue(item["is_stalled"])
        self.assertTrue(item["circuit_breaker_triggered"])
        self.assertEqual(item["status"], "PAUSED")
        self.assertEqual(item["quota_percent"], 100.0)

if __name__ == "__main__":
    unittest.main()
