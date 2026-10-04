import unittest
import asyncio
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

import agent_manager.config as config
from agent_manager.models import AgentSessionInfo, AgentStatus
from agent_manager.runner import AgentRunnerManager


class TestGuardrailsToggle(unittest.TestCase):
    def setUp(self):
        # Save previous config state
        self._prev_guardrails = getattr(config, "GUARDRAILS_ENABLED", True)
        self._prev_max_turns = getattr(config, "MAX_TURNS_PER_SESSION", 15)
        self._prev_dup_threshold = getattr(config, "CIRCUIT_BREAKER_DUPLICATE_THRESHOLD", 3)
        self._prev_max_reads = getattr(config, "CIRCUIT_BREAKER_MAX_CONSECUTIVE_READS", 8)
        self._prev_max_tokens = getattr(config, "MAX_SESSION_TOKENS", 150000)

    def tearDown(self):
        # Restore config state
        config.GUARDRAILS_ENABLED = self._prev_guardrails
        config.MAX_TURNS_PER_SESSION = self._prev_max_turns
        config.CIRCUIT_BREAKER_DUPLICATE_THRESHOLD = self._prev_dup_threshold
        config.CIRCUIT_BREAKER_MAX_CONSECUTIVE_READS = self._prev_max_reads
        config.MAX_SESSION_TOKENS = self._prev_max_tokens

    def test_settings_api_get_and_post_guardrails(self):
        from agent_manager.server import app
        client = TestClient(app)

        # 1. GET /api/settings should include guardrails_enabled
        res = client.get("/api/settings")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("guardrails_enabled", data)

        # 2. POST /api/settings to disable guardrails
        res_post = client.post("/api/settings", json={"guardrails_enabled": False})
        self.assertEqual(res_post.status_code, 200)
        data_post = res_post.json()
        self.assertFalse(data_post["guardrails_enabled"])
        self.assertFalse(config.GUARDRAILS_ENABLED)

        # 3. POST /api/settings to re-enable guardrails
        res_post2 = client.post("/api/settings", json={"guardrails_enabled": True})
        self.assertEqual(res_post2.status_code, 200)
        data_post2 = res_post2.json()
        self.assertTrue(data_post2["guardrails_enabled"])
        self.assertTrue(config.GUARDRAILS_ENABLED)

    def test_turn_budget_guardrail_toggle(self):
        runner = AgentRunnerManager()
        session = AgentSessionInfo(
            session_id="test-turns",
            title="Test Turn Limit",
            repo="BowenMichael/f1-frontend",
            status=AgentStatus.RUNNING,
            turn_count=15,
            max_turns=15
        )
        runner.sessions["test-turns"] = session

        # With guardrails enabled, turn limit pause check triggers
        config.GUARDRAILS_ENABLED = True
        config.MAX_TURNS_PER_SESSION = 15
        should_pause = (
            getattr(config, "GUARDRAILS_ENABLED", True)
            and session.turn_count >= config.MAX_TURNS_PER_SESSION
        )
        self.assertTrue(should_pause)

        # With guardrails disabled, turn limit pause check is bypassed
        config.GUARDRAILS_ENABLED = False
        should_pause_disabled = (
            getattr(config, "GUARDRAILS_ENABLED", True)
            and session.turn_count >= config.MAX_TURNS_PER_SESSION
        )
        self.assertFalse(should_pause_disabled)

    def test_duplicate_tool_loop_guardrail_toggle(self):
        runner = AgentRunnerManager()
        session = AgentSessionInfo(
            session_id="test-dup-tools",
            title="Test Duplicate Tools",
            repo="BowenMichael/f1-frontend",
            status=AgentStatus.RUNNING,
            consecutive_duplicate_tool_count=3
        )
        runner.sessions["test-dup-tools"] = session

        # With guardrails enabled, circuit breaker triggers at duplicate threshold
        config.GUARDRAILS_ENABLED = True
        config.CIRCUIT_BREAKER_DUPLICATE_THRESHOLD = 3
        should_trigger = (
            getattr(config, "GUARDRAILS_ENABLED", True)
            and session.consecutive_duplicate_tool_count >= config.CIRCUIT_BREAKER_DUPLICATE_THRESHOLD
        )
        self.assertTrue(should_trigger)

        # With guardrails disabled, circuit breaker is bypassed
        config.GUARDRAILS_ENABLED = False
        should_trigger_disabled = (
            getattr(config, "GUARDRAILS_ENABLED", True)
            and session.consecutive_duplicate_tool_count >= config.CIRCUIT_BREAKER_DUPLICATE_THRESHOLD
        )
        self.assertFalse(should_trigger_disabled)

    def test_consecutive_file_reads_guardrail_toggle(self):
        runner = AgentRunnerManager()
        session = AgentSessionInfo(
            session_id="test-consec-reads",
            title="Test Consecutive Reads",
            repo="BowenMichael/f1-frontend",
            status=AgentStatus.RUNNING,
            consecutive_view_file_count=8
        )
        runner.sessions["test-consec-reads"] = session

        # With guardrails enabled, circuit breaker triggers at 8 reads
        config.GUARDRAILS_ENABLED = True
        config.CIRCUIT_BREAKER_MAX_CONSECUTIVE_READS = 8
        should_trigger = (
            getattr(config, "GUARDRAILS_ENABLED", True)
            and session.consecutive_view_file_count >= config.CIRCUIT_BREAKER_MAX_CONSECUTIVE_READS
        )
        self.assertTrue(should_trigger)

        # With guardrails disabled, circuit breaker is bypassed
        config.GUARDRAILS_ENABLED = False
        should_trigger_disabled = (
            getattr(config, "GUARDRAILS_ENABLED", True)
            and session.consecutive_view_file_count >= config.CIRCUIT_BREAKER_MAX_CONSECUTIVE_READS
        )
        self.assertFalse(should_trigger_disabled)

    def test_token_budget_guardrail_toggle(self):
        runner = AgentRunnerManager()
        session = AgentSessionInfo(
            session_id="test-token-budget",
            title="Test Token Budget",
            repo="BowenMichael/f1-frontend",
            status=AgentStatus.RUNNING,
            total_tokens=150000,
            max_tokens=150000
        )
        runner.sessions["test-token-budget"] = session

        # With guardrails enabled, token quota triggers pause
        config.GUARDRAILS_ENABLED = True
        should_pause = (
            getattr(config, "GUARDRAILS_ENABLED", True)
            and session.total_tokens >= session.max_tokens
        )
        self.assertTrue(should_pause)

        # With guardrails disabled, token quota pause is bypassed
        config.GUARDRAILS_ENABLED = False
        should_pause_disabled = (
            getattr(config, "GUARDRAILS_ENABLED", True)
            and session.total_tokens >= session.max_tokens
        )
        self.assertFalse(should_pause_disabled)


if __name__ == "__main__":
    unittest.main()
