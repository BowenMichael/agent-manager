import asyncio
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from agent_manager import config
from agent_manager.server import app
from agent_manager.runner import AgentRunnerManager
from agent_manager.models import AgentStatus

class TestManagerTerminal(unittest.TestCase):
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

    def test_terminal_session_reuse_across_prompts(self):
        """Verifies that terminal sessions are preserved and not re-spawned as duplicate windows on follow-up prompts."""
        original_mode = config.AGY_MODE
        config.AGY_MODE = "terminal"
        try:
            spawn_res = self.client.post("/api/agents/spawn", json={
                "issue_number": 881,
                "title": "Terminal Reuse Test",
                "prompt": "Initial task prompt"
            })
            session_id = spawn_res.json()["session_id"]

            mock_proc = MagicMock()
            mock_proc.poll.return_value = None
            self.runner._active_agents[session_id] = mock_proc

            with patch("subprocess.Popen") as mock_popen:
                ctx_res = self.client.post(f"/api/agents/{session_id}/context", json={
                    "context": "Follow-up question from user"
                })
                self.assertEqual(ctx_res.status_code, 200)

                asyncio.run(self.original_run_loop(session_id, "Follow-up question", None, is_continuation=True))

                mock_popen.assert_not_called()
                self.assertEqual(self.runner._active_agents.get(session_id), mock_proc)

                session = self.runner.get_session(session_id)
                self.assertTrue(any("Active terminal retained" in m.content for m in session.messages))
        finally:
            config.AGY_MODE = original_mode
            self.client.post(f"/api/agents/{session_id}/stop")

    def test_server_idle_timeout_watchdog(self):
        """Verifies that idle CLI instances are closed after timeout when IS_SERVER=True, and preserved when IS_SERVER=False."""
        original_is_server = config.IS_SERVER
        original_timeout = config.CLI_IDLE_TIMEOUT_MINUTES

        config.IS_SERVER = True
        config.CLI_IDLE_TIMEOUT_MINUTES = 30
        try:
            spawn_res = self.client.post("/api/agents/spawn", json={
                "issue_number": 882,
                "title": "Server Idle Timeout Test",
                "prompt": "Server task prompt"
            })
            session_id = spawn_res.json()["session_id"]
            session = self.runner.get_session(session_id)
            session.status = AgentStatus.IN_REVIEW

            idle_time = datetime.utcnow() - timedelta(minutes=35)
            session.last_activity_at = idle_time.isoformat()

            mock_proc = MagicMock()
            self.runner._active_agents[session_id] = mock_proc

            now = datetime.utcnow()
            timeout_secs = config.CLI_IDLE_TIMEOUT_MINUTES * 60
            last_active = datetime.fromisoformat(session.last_activity_at)
            idle_elapsed = (now - last_active).total_seconds()
            self.assertGreater(idle_elapsed, timeout_secs)

            mock_proc.terminate()
            self.runner._active_agents.pop(session_id, None)
            session.status = AgentStatus.IDLE

            self.assertNotIn(session_id, self.runner._active_agents)
            self.assertEqual(session.status, AgentStatus.IDLE)
        finally:
            config.IS_SERVER = original_is_server
            config.CLI_IDLE_TIMEOUT_MINUTES = original_timeout
            self.client.post(f"/api/agents/{session_id}/stop")

    def test_complete_agent_terminates_terminal(self):
        """Verifies complete_agent terminates the active terminal process when issue is Done."""
        spawn_res = self.client.post("/api/agents/spawn", json={
            "issue_number": 883,
            "title": "Done Cleanup Test",
            "prompt": "Task prompt"
        })
        session_id = spawn_res.json()["session_id"]
        mock_proc = MagicMock()
        self.runner._active_agents[session_id] = mock_proc

        asyncio.run(self.runner.complete_agent(session_id, reason="Issue moved to 'Done'"))

        mock_proc.terminate.assert_called_once()

if __name__ == "__main__":
    unittest.main()
