"""
Unit & Integration Tests for USD Cost Estimator & Session Replay Service.
Verifies model rate card resolution, token pricing math, spend aggregation,
replay artifact generation, and REST endpoint integration.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from agent_manager.server import app
from agent_manager.models import (
    AgentSessionInfo, AgentStatus, ConversationMessage, MessageRole
)
from agent_manager.services.cost_calculator_service import (
    get_rate_card, calculate_token_cost, calculate_session_cost,
    generate_cost_telemetry_summary
)
from agent_manager.services.session_replay_service import (
    build_session_replay, save_session_replay, load_session_replay
)
import agent_manager.services.session_replay_service as srs
from agent_manager.storage import save_single_session


class TestCostCalculatorService(unittest.TestCase):
    def test_get_rate_card(self):
        flash_rates = get_rate_card("gemini-2.5-flash")
        self.assertEqual(flash_rates["input"], 0.075)
        self.assertEqual(flash_rates["output"], 0.30)

        claude_rates = get_rate_card("claude-3-5-sonnet")
        self.assertEqual(claude_rates["input"], 3.00)

        default_rates = get_rate_card("unknown-experimental-model")
        self.assertEqual(default_rates["input"], 1.00)

    def test_calculate_token_cost(self):
        # 1M input tokens + 1M output tokens on gemini-2.5-flash = 0.075 + 0.30 = $0.375
        cost = calculate_token_cost("gemini-2.5-flash", 1_000_000, 1_000_000)
        self.assertAlmostEqual(cost, 0.375, places=4)

        # Partial tokens
        cost_partial = calculate_token_cost("gemini-2.5-flash", 500_000, 200_000)
        expected = (0.5 * 0.075) + (0.2 * 0.30)
        self.assertAlmostEqual(cost_partial, round(expected, 6), places=5)

    def test_calculate_session_cost_and_summary(self):
        s1 = AgentSessionInfo(
            session_id="sess-cost-1",
            repo="BowenMichael/agent-manager",
            title="Session 1",
            model="gemini-2.5-flash",
            input_tokens=100_000,
            output_tokens=50_000,
            duration_seconds=3600.0
        )
        s2 = AgentSessionInfo(
            session_id="sess-cost-2",
            repo="BowenMichael/fitelo",
            title="Session 2",
            model="claude-3-5-sonnet",
            input_tokens=50_000,
            output_tokens=10_000,
            duration_seconds=1800.0
        )

        cost1 = calculate_session_cost(s1)
        self.assertGreater(cost1, 0.0)

        summary = generate_cost_telemetry_summary([s1, s2])
        self.assertGreater(summary["total_spend_usd"], 0.0)
        self.assertIn("BowenMichael/agent-manager", summary["cost_by_repo"])
        self.assertIn("BowenMichael/fitelo", summary["cost_by_repo"])
        self.assertGreater(summary["burn_rate_hourly_usd"], 0.0)


class TestSessionReplayService(unittest.TestCase):
    def test_build_and_load_session_replay(self):
        session = AgentSessionInfo(
            session_id="replay-test-sess",
            repo="BowenMichael/agent-manager",
            title="Replay Test",
            messages=[
                ConversationMessage(id="m1", role=MessageRole.USER, content="Run unit tests"),
                ConversationMessage(id="m2", role=MessageRole.AGENT, content="Tests completed")
            ]
        )

        replay = build_session_replay(session)
        self.assertEqual(replay["session_id"], "replay-test-sess")
        self.assertEqual(replay["total_frames"], 2)
        self.assertEqual(replay["frames"][0]["role"], "USER")

        with tempfile.TemporaryDirectory() as tmp_dir:
            orig_dir = srs.REPLAYS_DIR
            srs.REPLAYS_DIR = Path(tmp_dir)
            try:
                saved_path = save_session_replay(session)
                self.assertTrue(saved_path.exists())

                loaded = load_session_replay("replay-test-sess")
                self.assertIsNotNone(loaded)
                self.assertEqual(loaded["total_frames"], 2)
            finally:
                srs.REPLAYS_DIR = orig_dir


class TestTelemetryCostAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_get_cost_summary_endpoint(self):
        res = self.client.get("/api/telemetry/cost-summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_spend_usd", data)
        self.assertIn("cost_by_repo", data)

    def test_get_session_replay_endpoint(self):
        sess = AgentSessionInfo(
            session_id="api-replay-sess",
            repo="BowenMichael/agent-manager",
            title="API Replay Test",
            status=AgentStatus.COMPLETED,
            messages=[ConversationMessage(id="msg-1", role=MessageRole.AGENT, content="Done")]
        )
        save_single_session(sess)

        res = self.client.get("/api/sessions/api-replay-sess/replay")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["session_id"], "api-replay-sess")
        self.assertEqual(len(data["frames"]), 1)


if __name__ == "__main__":
    unittest.main()
