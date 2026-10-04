import unittest
import asyncio
import tempfile
import json
import os
import sys
from pathlib import Path
from agent_manager.models import AgentSessionInfo, AgentStatus, MessageRole
from agent_manager.runners.process_manager import is_process_alive, launch_detached_agent, terminate_process
from agent_manager.runners.stream_tailer import tail_agent_log


class DummyManager:
    def __init__(self, sessions):
        self.sessions = sessions
        self._saved = False
        self.broadcast_events = []
        self.added_messages = []

    def _save(self):
        self._saved = True

    async def broadcast(self, event_type, data):
        self.broadcast_events.append((event_type, data))

    async def _append_message(self, session_id, role, content, **kwargs):
        self.added_messages.append((session_id, role, content))
        if session_id in self.sessions:
            self.sessions[session_id].messages.append(type("Msg", (), {"role": role, "content": content})())

    async def _broadcast_token(self, session_id, token):
        pass

    async def _flag_quota_exceeded(self, session_id, detail):
        pass

    async def compact_session(self, session_id):
        pass

    async def complete_agent(self, session_id, reason=""):
        pass


class TestDecoupledExecution(unittest.TestCase):
    def test_process_manager_alive_and_terminate(self):
        my_pid = os.getpid()
        self.assertTrue(is_process_alive(my_pid))
        self.assertFalse(is_process_alive(-99999))

    def test_detached_worker_launch_and_tail(self):
        async def run_test():
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                log_file = tmp_path / "test.stream.jsonl"
                exit_file = tmp_path / "test.exitcode"

                # Write events directly to log file and exit file, testing tail_agent_log
                first_event = json.dumps({"event": "step_update", "step_update": {"step_type": "agent_response", "text_delta": "Hello decoupled world!", "state": "DONE"}}) + "\n"
                second_event = json.dumps({"event": "result", "result": {"response": "Completed detached execution."}}) + "\n"
                log_file.write_text(first_event + second_event, encoding="utf-8")
                exit_file.write_text("0", encoding="utf-8")

                session = AgentSessionInfo(
                    session_id="test-session-123",
                    repo="test/repo",
                    title="Test Detached",
                    status=AgentStatus.RUNNING,
                    pid=99999999,  # completed process
                    stream_log_file=str(log_file),
                    exit_code_file=str(exit_file),
                    stream_log_offset=0
                )
                manager = DummyManager({"test-session-123": session})

                await tail_agent_log(manager, "test-session-123")

                self.assertIn(session.status, [AgentStatus.IN_REVIEW, AgentStatus.COMPLETED])
                self.assertTrue(any("Hello decoupled world!" in m[2] for m in manager.added_messages))
                self.assertTrue(exit_file.exists())
                self.assertEqual(exit_file.read_text().strip(), "0")

        asyncio.run(run_test())

    def test_reattachment_state_recovery(self):
        async def run_reattach_test():
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                log_file = tmp_path / "reattach.stream.jsonl"
                exit_file = tmp_path / "reattach.exitcode"

                # Write pre-existing lines into the log
                first_event = json.dumps({"event": "step_update", "step_update": {"step_type": "agent_response", "text_delta": "First part", "state": "DONE"}}) + "\n"
                log_file.write_text(first_event, encoding="utf-8")
                initial_offset = log_file.stat().st_size

                # Append second event
                second_event = json.dumps({"event": "result", "result": {"response": "Second part finished."}}) + "\n"
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(second_event)
                exit_file.write_text("0", encoding="utf-8")

                # Mock session that starts at initial_offset (simulating server crash/reboot after first part)
                session = AgentSessionInfo(
                    session_id="reattach-session",
                    repo="test/repo",
                    title="Test Reattach",
                    status=AgentStatus.RUNNING,
                    pid=99999999,
                    stream_log_file=str(log_file),
                    exit_code_file=str(exit_file),
                    stream_log_offset=initial_offset
                )
                manager = DummyManager({"reattach-session": session})

                await tail_agent_log(manager, "reattach-session")

                # It should process the second event from the offset without repeating the first
                self.assertFalse(any("First part" in m[2] for m in manager.added_messages))
                self.assertTrue(any("Second part finished." in m[2] for m in manager.added_messages))
                self.assertEqual(session.status, AgentStatus.IN_REVIEW)

        asyncio.run(run_reattach_test())


if __name__ == "__main__":
    unittest.main()
