import os
import sys
import json
import time
import asyncio
import tempfile
import unittest
from pathlib import Path

from agent_manager.models import AgentSessionInfo, AgentStatus
from agent_manager.storage import save_sessions, load_sessions, save_single_session, SESSIONS_FILE
from agent_manager.runners.process_manager import is_process_alive, terminate_process, launch_independent_agent_service
from agent_manager.runner import AgentRunnerManager
from agent_manager.runners.stream_tailer import tail_agent_log


class TestIndependentAgentService(unittest.TestCase):
    """Verifies that agents run as independent services and survive server restarts."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_single_session_isolated_update(self):
        """Verifies that save_single_session updates only the target session without clobbering others."""
        s1 = AgentSessionInfo(session_id="s1", title="Task 1", status=AgentStatus.RUNNING, repo="repo/one")
        s2 = AgentSessionInfo(session_id="s2", title="Task 2", status=AgentStatus.IN_REVIEW, repo="repo/two")
        save_sessions({"s1": s1, "s2": s2})

        s1_updated = AgentSessionInfo(session_id="s1", title="Task 1", status=AgentStatus.COMPLETED, repo="repo/one")
        save_single_session(s1_updated)

        loaded = load_sessions()
        self.assertEqual(loaded["s1"].status, AgentStatus.COMPLETED)
        self.assertEqual(loaded["s2"].status, AgentStatus.IN_REVIEW)

    def test_server_restart_preserves_running_status_if_pid_alive(self):
        """Verifies that load_sessions preserves RUNNING status if the detached PID is alive."""
        # Use current process PID as a surrogate for an active daemon process
        current_pid = os.getpid()
        s_alive = AgentSessionInfo(session_id="alive-sess", title="Alive Task", status=AgentStatus.RUNNING, repo="repo/test", pid=current_pid)
        save_sessions({"alive-sess": s_alive})

        loaded = load_sessions()
        self.assertEqual(loaded["alive-sess"].status, AgentStatus.RUNNING)
        self.assertEqual(loaded["alive-sess"].pid, current_pid)

    def test_server_restart_recovers_to_in_review_if_pid_dead(self):
        """Verifies that load_sessions transitions dead agent processes to IN_REVIEW with cache restored notice."""
        fake_dead_pid = 99999999
        s_dead = AgentSessionInfo(session_id="dead-sess", title="Dead Task", status=AgentStatus.RUNNING, repo="repo/test", pid=fake_dead_pid)
        save_sessions({"dead-sess": s_dead})

        loaded = load_sessions()
        self.assertEqual(loaded["dead-sess"].status, AgentStatus.IN_REVIEW)
        self.assertTrue(any("Task Cache Restored" in m.content for m in loaded["dead-sess"].messages))

    def test_tail_agent_log_cancellation_preserves_running_state(self):
        """Verifies that when tail_agent_log is cancelled on server restart, the session stays RUNNING."""
        log_file = self.tmp_path / "stream.jsonl"
        log_file.write_text(json.dumps({"event": "step_update", "step_update": {"step_type": "text", "state": "running"}}) + "\n", encoding="utf-8")

        current_pid = os.getpid()
        session = AgentSessionInfo(
            session_id="cancel-sess",
            title="Cancel Task",
            repo="repo/test",
            status=AgentStatus.RUNNING,
            pid=current_pid,
            stream_log_file=str(log_file)
        )

        manager = AgentRunnerManager()
        manager.sessions["cancel-sess"] = session

        async def run_cancel_test():
            task = asyncio.create_task(tail_agent_log(manager, "cancel-sess"))
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(run_cancel_test())
        # Since os.getpid() is alive, session status must remain RUNNING!
        self.assertEqual(manager.sessions["cancel-sess"].status, AgentStatus.RUNNING)


if __name__ == "__main__":
    unittest.main()
