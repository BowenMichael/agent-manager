import asyncio
import unittest
from fastapi.testclient import TestClient

from agent_manager.server import app
from agent_manager.runner import AgentRunnerManager
from agent_manager.models import AgentStatus, MessageRole

class TestManagerCompaction(unittest.TestCase):
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

    def test_chat_compaction_and_auto_compression(self):
        # 1. Spawn agent
        spawn_res = self.client.post("/api/agents/spawn", json={
            "issue_number": 995,
            "title": "Compaction Test Task",
            "prompt": "Build feature and run verification tests"
        })
        self.assertEqual(spawn_res.status_code, 200)
        session_id = spawn_res.json()["session_id"]

        session = self.runner.get_session(session_id)
        # Add intermediate verbose messages: tool calls, tool results, thoughts
        asyncio.run(self.runner._append_message(session_id, MessageRole.TOOL_CALL, "git status", tool_name="run_command"))
        asyncio.run(self.runner._append_message(session_id, MessageRole.TOOL_RESULT, "On branch feat/issue-995\nnothing to commit", tool_name="run_command"))
        asyncio.run(self.runner._append_message(session_id, MessageRole.THOUGHT, "Inspecting files and preparing changes..."))
        asyncio.run(self.runner._append_message(session_id, MessageRole.TOOL_CALL, "npm test", tool_name="run_command"))
        asyncio.run(self.runner._append_message(session_id, MessageRole.TOOL_RESULT, "Tests passed: 42 passed", tool_name="run_command"))
        asyncio.run(self.runner._append_message(session_id, MessageRole.AGENT, "All changes implemented and validated."))

        # Verify messages before compaction
        self.assertGreater(len(session.messages), 5)
        self.assertFalse(session.is_compacted)

        # 2. Test manual compaction via API
        compact_res = self.client.post(f"/api/agents/{session_id}/compact")
        self.assertEqual(compact_res.status_code, 200)
        self.assertTrue(compact_res.json()["is_compacted"])

        # Verify session is now compacted
        compacted_session = self.client.get(f"/api/agents/{session_id}").json()
        self.assertTrue(compacted_session["is_compacted"])
        self.assertIsNotNone(compacted_session["compact_summary"])
        # Should retain: initial user prompt, compacted summary, and final agent response
        self.assertLess(len(compacted_session["messages"]), 5)
        self.assertTrue(any("Chat Compacted & Compressed" in m["content"] for m in compacted_session["messages"]))

        # 3. Test auto-compaction on process completion
        spawn_res2 = self.client.post("/api/agents/spawn", json={
            "issue_number": 996,
            "title": "Auto-Compaction Completion Task",
            "prompt": "Execute deployment pipeline"
        })
        self.assertEqual(spawn_res2.status_code, 200)
        session_id2 = spawn_res2.json()["session_id"]
        asyncio.run(self.runner._append_message(session_id2, MessageRole.TOOL_CALL, "deploy", tool_name="run_command"))
        asyncio.run(self.runner._append_message(session_id2, MessageRole.TOOL_RESULT, "Deployed successfully", tool_name="run_command"))
        asyncio.run(self.runner._append_message(session_id2, MessageRole.AGENT, "Deployment finished."))

        # Mark done / complete
        complete_res = self.client.post(f"/api/agents/{session_id2}/complete")
        self.assertEqual(complete_res.status_code, 200)

        completed_session2 = self.client.get(f"/api/agents/{session_id2}").json()
        self.assertEqual(completed_session2["status"], AgentStatus.COMPLETED.value)
        self.assertTrue(completed_session2["is_compacted"])
        self.assertIsNotNone(completed_session2["compact_summary"])

if __name__ == "__main__":
    unittest.main()
