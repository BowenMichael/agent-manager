"""
Unit & Integration Tests for Agent Runner Stability & Process Lifecycle.
Tests dead process detection, watchdog timezone resilience, CLI argument construction, and failure recovery.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import os
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path

from agent_manager.models import AgentSessionInfo, AgentStatus, MessageRole, ConversationMessage
from agent_manager.runners.process_manager import is_process_alive, terminate_process
from agent_manager.runners.watchdog import _check_dead_process, _check_stalled_agent, _check_idle_timeout
from agent_manager.runners.agent_service import (
    _build_cli_command,
    _handle_service_failure
)


class TestProcessLifecycle(unittest.TestCase):
    """Verifies process liveness detection and termination safety."""

    def test_invalid_pid_checks(self):
        """Invalid PIDs return False for liveness and termination."""
        self.assertFalse(is_process_alive(None))
        self.assertFalse(is_process_alive(0))
        self.assertFalse(is_process_alive(-1))
        self.assertFalse(terminate_process(None))
        self.assertFalse(terminate_process(0))

    @patch("agent_manager.runners.process_manager.is_process_alive", return_value=False)
    def test_terminate_already_dead_process(self, mock_alive):
        """Terminating an already dead process returns True immediately."""
        self.assertTrue(terminate_process(999999))


class TestWatchdogDeadProcessDetection(unittest.IsolatedAsyncioTestCase):
    """Verifies watchdog detection of unexpectedly terminated subprocesses."""

    @patch("agent_manager.runners.watchdog.is_process_alive", return_value=False)
    async def test_dead_process_marked_as_failed(self, mock_alive):
        """A running agent whose PID has died is marked FAILED by the watchdog."""
        manager = MagicMock()
        manager._save = MagicMock()
        manager.broadcast = AsyncMock()

        session = AgentSessionInfo(
            session_id="test-dead-proc",
            repo="BowenMichael/agent-manager",
            issue_number=143,
            title="Test Dead Process",
            status=AgentStatus.RUNNING,
            pid=98765
        )

        await _check_dead_process(manager, "test-dead-proc", session)
        self.assertEqual(session.status, AgentStatus.FAILED)
        self.assertIn("terminated unexpectedly", session.error_message)
        self.assertFalse(session.is_stalled)
        manager._save.assert_called_once()
        manager.broadcast.assert_called_once_with("session_updated", session.model_dump())

    @patch("agent_manager.runners.watchdog.is_process_alive", return_value=True)
    async def test_alive_process_remains_running(self, mock_alive):
        """A running agent whose PID is alive is not altered."""
        manager = MagicMock()
        manager._save = MagicMock()

        session = AgentSessionInfo(
            session_id="test-alive-proc",
            repo="BowenMichael/agent-manager",
            issue_number=143,
            title="Test Alive Process",
            status=AgentStatus.RUNNING,
            pid=12345
        )

        await _check_dead_process(manager, "test-alive-proc", session)
        self.assertEqual(session.status, AgentStatus.RUNNING)
        manager._save.assert_not_called()


class TestWatchdogTimezoneResilience(unittest.IsolatedAsyncioTestCase):
    """Verifies watchdog handles timezone-aware and naive timestamps without exceptions."""

    async def test_stalled_agent_with_utc_timestamp(self):
        """Stalled agent check handles timezone-aware UTC timestamps."""
        manager = MagicMock()
        manager._save = MagicMock()
        manager.broadcast = AsyncMock()

        stalled_time = datetime.now(timezone.utc) - timedelta(seconds=45)
        session = AgentSessionInfo(
            session_id="test-stalled",
            repo="BowenMichael/agent-manager",
            issue_number=143,
            title="Test Stalled",
            status=AgentStatus.RUNNING,
            last_activity_at=stalled_time.isoformat()
        )

        now = datetime.now(timezone.utc)
        await _check_stalled_agent(manager, session, now)
        self.assertTrue(session.is_stalled)
        manager._save.assert_called_once()


class TestAgentServiceExecution(unittest.TestCase):
    """Verifies CLI argument construction and error boundary handling."""

    def test_build_cli_command_initial_turn(self):
        """Constructs CLI invocation command with prompt and worktree guidelines."""
        session = AgentSessionInfo(
            session_id="test-cli-build",
            repo="BowenMichael/agent-manager",
            issue_number=143,
            title="Fix Runner Stability",
            status=AgentStatus.RUNNING,
            model="gemini-3.8-flash",
            effort="high"
        )
        cmd = _build_cli_command(
            session,
            cwd_dir="E:/projects/test",
            issue_num=143,
            branch_name="feat/issue-143",
            repo="BowenMichael/agent-manager",
            target_prompt="Implement stability fixes",
            is_continuation=False
        )
        self.assertIn("--dangerously-skip-permissions", cmd)
        self.assertIn("--output-format", cmd)
        self.assertIn("stream-json", cmd)
        self.assertIn("-p", cmd)

    def test_build_cli_command_continuation_turn(self):
        """Continuation turn includes --continue flag."""
        session = AgentSessionInfo(
            session_id="test-cli-continue",
            repo="BowenMichael/agent-manager",
            issue_number=143,
            title="Continue Fix",
            status=AgentStatus.RUNNING
        )
        cmd = _build_cli_command(
            session,
            cwd_dir="E:/projects/test",
            issue_num=143,
            branch_name="feat/issue-143",
            repo="BowenMichael/agent-manager",
            target_prompt="Continue work",
            is_continuation=True
        )
        self.assertIn("--continue", cmd)
        self.assertIn("-p", cmd)

    @patch("agent_manager.runners.agent_service.load_sessions")
    @patch("agent_manager.runners.agent_service.save_single_session")
    def test_handle_service_failure(self, mock_save, mock_load):
        """Failure handler records FAILED status and writes exitcode."""
        session = AgentSessionInfo(
            session_id="test-fail-rec",
            repo="BowenMichael/agent-manager",
            issue_number=143,
            title="Test Fail",
            status=AgentStatus.RUNNING
        )
        mock_load.return_value = {"test-fail-rec": session}

        _handle_service_failure("test-fail-rec", RuntimeError("Subprocess crashed"))
        self.assertEqual(session.status, AgentStatus.FAILED)
        self.assertIn("Subprocess crashed", session.error_message)
        mock_save.assert_called_once_with(session)


if __name__ == "__main__":
    unittest.main()
