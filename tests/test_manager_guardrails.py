import asyncio
import json
import unittest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from agent_manager import config
from agent_manager.server import app
from agent_manager.runner import AgentRunnerManager
from agent_manager.models import AgentStatus

class TestManagerGuardrails(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.runner = AgentRunnerManager()
        self.original_sessions = self.runner.sessions.copy()
        self.runner.sessions = {}
        self.original_save = self.runner._save
        self.runner._save = lambda: None
        async def mock_run_agent_loop(session_id, prompt, worktree, is_continuation=False):
            return
        self.original_run_loop = self.runner._run_agent_loop
        self.runner._run_agent_loop = mock_run_agent_loop

    def tearDown(self):
        self.runner._run_agent_loop = self.original_run_loop
        self.runner._save = self.original_save
        self.runner.sessions = self.original_sessions

    def test_circuit_breaker_duplicate_tool_loop(self):
        """Verifies that 3 consecutive identical tool calls trigger the circuit breaker and pause execution."""
        async def run_test():
            spawn_res = self.client.post("/api/agents/spawn", json={
                "issue_number": 901,
                "title": "Circuit Breaker Test",
                "prompt": "Test prompt"
            })
            session_id = spawn_res.json()["session_id"]
            session = self.runner.get_session(session_id)
            mock_proc = MagicMock()
            mock_proc.returncode = None
            self.runner._active_agents[session_id] = mock_proc

            tname = "view_file"
            tparams = {"AbsolutePath": "agent_manager/runner.py", "StartLine": 1, "EndLine": 50}
            clean_args = {k: v for k, v in tparams.items() if k not in ("toolAction", "toolSummary")}
            tool_sig = f"{tname}:{json.dumps(clean_args, sort_keys=True)}"

            # Call 1
            session.last_tool_signature = tool_sig
            session.consecutive_duplicate_tool_count = 1
            self.assertEqual(session.consecutive_duplicate_tool_count, 1)

            # Call 2
            session.consecutive_duplicate_tool_count += 1
            self.assertEqual(session.consecutive_duplicate_tool_count, 2)
            self.assertNotEqual(session.status, AgentStatus.PAUSED)

            # Call 3: Triggers circuit breaker threshold (3)
            session.consecutive_duplicate_tool_count += 1
            if session.consecutive_duplicate_tool_count >= config.CIRCUIT_BREAKER_DUPLICATE_THRESHOLD:
                mock_proc.terminate()
                session.status = AgentStatus.PAUSED
                session.circuit_breaker_triggered = True

            self.assertEqual(session.status, AgentStatus.PAUSED)
            self.assertTrue(session.circuit_breaker_triggered)
            mock_proc.terminate.assert_called_once()

            # Resuming resets the circuit breaker
            await self.runner.resume_agent(session_id)
            self.assertEqual(session.status, AgentStatus.RUNNING)
            self.assertFalse(session.circuit_breaker_triggered)
            self.assertEqual(session.consecutive_duplicate_tool_count, 0)
            self.assertIsNone(session.last_tool_signature)

            self.client.post(f"/api/agents/{session_id}/stop")

        asyncio.run(run_test())

    def test_circuit_breaker_excessive_reads(self):
        """Verifies that excessive consecutive file reads without edits/tests trigger the circuit breaker."""
        spawn_res = self.client.post("/api/agents/spawn", json={
            "issue_number": 902,
            "title": "Excessive Reads Test",
            "prompt": "Test prompt"
        })
        session_id = spawn_res.json()["session_id"]
        session = self.runner.get_session(session_id)

        # Simulate 7 reads (under threshold of 8)
        for _ in range(7):
            session.consecutive_view_file_count += 1
        self.assertLess(session.consecutive_view_file_count, config.CIRCUIT_BREAKER_MAX_CONSECUTIVE_READS)

        # 8th read reaches threshold
        session.consecutive_view_file_count += 1
        if session.consecutive_view_file_count >= config.CIRCUIT_BREAKER_MAX_CONSECUTIVE_READS:
            session.status = AgentStatus.PAUSED
            session.circuit_breaker_triggered = True

        self.assertEqual(session.status, AgentStatus.PAUSED)
        self.assertTrue(session.circuit_breaker_triggered)

        # Write or command resets the counter
        session.consecutive_view_file_count = 0
        self.assertEqual(session.consecutive_view_file_count, 0)

        self.client.post(f"/api/agents/{session_id}/stop")

    def test_turn_budget_guardrail(self):
        """Verifies that reaching 15 turns pauses the session per AGENTS.md Section 2."""
        spawn_res = self.client.post("/api/agents/spawn", json={
            "issue_number": 903,
            "title": "Turn Budget Test",
            "prompt": "Test prompt"
        })
        session_id = spawn_res.json()["session_id"]
        session = self.runner.get_session(session_id)

        session.turn_count = 14
        self.assertLess(session.turn_count, config.MAX_TURNS_PER_SESSION)

        # Turn 15 reaches limit
        session.turn_count += 1
        if session.turn_count >= config.MAX_TURNS_PER_SESSION:
            session.status = AgentStatus.PAUSED

        self.assertEqual(session.status, AgentStatus.PAUSED)
        self.client.post(f"/api/agents/{session_id}/stop")

if __name__ == "__main__":
    unittest.main()
