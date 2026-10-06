"""
Unit tests for Agent Runner Lifecycle, Process Management, and Watchdog Monitors.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

from agent_manager.models import AgentSessionInfo, AgentStatus, MessageRole
from agent_manager.runners.process_manager import is_process_alive, terminate_process
from agent_manager.runners.watchdog import (
    _check_stalled_agent,
    _check_idle_timeout,
    interrupt_agent,
    flag_quota_exceeded
)
from agent_manager.runners.terminal_launcher import _build_windows_script


class TestRunnerLifecycleAndWatchdog(unittest.IsolatedAsyncioTestCase):
    """Test suite for agent runner lifecycle, watchdog monitoring, and process management."""

    def test_process_alive_and_terminate_invalid_pid(self):
        """Verify process management functions handle invalid PIDs gracefully."""
        self.assertFalse(is_process_alive(None))
        self.assertFalse(is_process_alive(-1))
        self.assertFalse(is_process_alive(0))
        self.assertFalse(terminate_process(None))
        self.assertFalse(terminate_process(-1))

    async def test_watchdog_detects_stalled_agent(self):
        """Verify watchdog flags agent as stalled if activity is older than 30s."""
        manager = MagicMock()
        manager._save = MagicMock()
        manager.broadcast = AsyncMock()

        session = AgentSessionInfo(
            session_id="test_session_1",
            repo="BowenMichael/agent-manager",
            issue_number=128,
            title="Test Issue",
            prompt="Test Prompt",
            status=AgentStatus.RUNNING,
            last_activity_at=(datetime.utcnow() - timedelta(seconds=45)).isoformat(),
            is_stalled=False
        )

        now = datetime.utcnow()
        await _check_stalled_agent(manager, session, now)

        self.assertTrue(session.is_stalled)
        self.assertIn("Unresponsive / Hung", session.current_activity)
        manager._save.assert_called_once()
        manager.broadcast.assert_called_once()

    async def test_watchdog_idle_timeout_closing(self):
        """Verify watchdog closes idle agent session on server mode."""
        manager = MagicMock()
        manager._save = MagicMock()
        manager.broadcast = AsyncMock()
        manager._append_message = AsyncMock()
        manager._active_agents = {}

        session = AgentSessionInfo(
            session_id="test_session_2",
            repo="BowenMichael/agent-manager",
            issue_number=128,
            title="Test Issue",
            prompt="Test Prompt",
            status=AgentStatus.RUNNING,
            last_activity_at=(datetime.utcnow() - timedelta(minutes=60)).isoformat(),
            pid=99999
        )

        now = datetime.utcnow()
        with patch("agent_manager.config.IS_SERVER", True), \
             patch("agent_manager.config.CLI_IDLE_TIMEOUT_MINUTES", 30), \
             patch("agent_manager.runners.watchdog.terminate_process", return_value=True):
            await _check_idle_timeout(manager, "test_session_2", session, now)

        self.assertEqual(session.status, AgentStatus.IDLE)
        self.assertIn("Idle CLI instance closed", session.current_activity)

    async def test_interrupt_agent(self):
        """Verify interrupt_agent safely halts agent and moves to IN_REVIEW."""
        manager = MagicMock()
        manager._save = MagicMock()
        manager.broadcast = AsyncMock()
        manager._active_agents = {}
        manager._tasks = {}

        session = AgentSessionInfo(
            session_id="test_session_3",
            repo="BowenMichael/agent-manager",
            issue_number=128,
            title="Test Issue",
            prompt="Test Prompt",
            status=AgentStatus.RUNNING
        )
        manager.sessions = {"test_session_3": session}

        success = await interrupt_agent(manager, "test_session_3")
        self.assertTrue(success)
        self.assertEqual(session.status, AgentStatus.IN_REVIEW)
        self.assertFalse(session.is_stalled)

    async def test_flag_quota_exceeded(self):
        """Verify flag_quota_exceeded pauses session and logs notification."""
        manager = MagicMock()
        manager._save = MagicMock()
        manager.broadcast = AsyncMock()
        manager._append_message = AsyncMock()

        session = AgentSessionInfo(
            session_id="test_session_4",
            repo="BowenMichael/agent-manager",
            issue_number=128,
            title="Test Issue",
            prompt="Test Prompt",
            status=AgentStatus.RUNNING
        )
        manager.sessions = {"test_session_4": session}

        await flag_quota_exceeded(manager, "test_session_4", "Resource exhausted: 429 rate limit")
        self.assertEqual(session.status, AgentStatus.PAUSED)
        self.assertIn("Quota / Rate Limit Exceeded", session.current_activity)

    def test_build_windows_script(self):
        """Verify Windows PowerShell terminal script generation contains prompt and model."""
        script = _build_windows_script(
            issue_num=128,
            clean_model="gemini-2.5-flash",
            clean_effort="high",
            cli_model_args=["--model", "gemini-2.5-flash"],
            target_prompt="Solve bug #128",
            is_continuation=False
        )
        self.assertIn("Issue #128", script)
        self.assertIn("gemini-2.5-flash", script)
        self.assertIn("Solve bug #128", script)

    def test_terminate_process_handles_already_dead_and_fallback(self):
        """Verify terminate_process returns True if process is not alive after taskkill."""
        with patch("agent_manager.runners.process_manager.is_process_alive", side_effect=[True, False]), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128)
            res = terminate_process(12345)
            self.assertTrue(res)


if __name__ == "__main__":
    unittest.main()
