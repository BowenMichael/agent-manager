import unittest
from fastapi.testclient import TestClient

from agent_manager.server import app
from agent_manager.runner import AgentRunnerManager

class TestManagerArchiving(unittest.TestCase):
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

    def test_agent_archive_and_unarchive(self):
        # 1. Spawn Agent
        spawn_res = self.client.post("/api/agents/spawn", json={
            "repo": "BowenMichael/agent-manager",
            "issue_number": 997,
            "title": "Agent to be archived",
            "prompt": "Test archiving capability"
        })
        self.assertEqual(spawn_res.status_code, 200)
        session_id = spawn_res.json()["session_id"]

        # 2. Check active listing includes the new agent
        active_list_res = self.client.get("/api/agents?include_archived=false")
        self.assertEqual(active_list_res.status_code, 200)
        active_ids = [s["session_id"] for s in active_list_res.json()]
        self.assertIn(session_id, active_ids)

        # 3. Archive the Agent
        archive_res = self.client.post(f"/api/agents/{session_id}/archive")
        self.assertEqual(archive_res.status_code, 200)

        # 4. Verify agent status and is_archived flag
        session_res = self.client.get(f"/api/agents/{session_id}")
        self.assertEqual(session_res.status_code, 200)
        session_data = session_res.json()
        self.assertTrue(session_data["is_archived"])
        self.assertIsNotNone(session_data["archived_at"])

        # 5. Verify agent is excluded from list when include_archived=false
        active_list_after = self.client.get("/api/agents?include_archived=false").json()
        active_ids_after = [s["session_id"] for s in active_list_after]
        self.assertNotIn(session_id, active_ids_after)

        # 6. Verify agent is included in full list
        all_list = self.client.get("/api/agents?include_archived=true").json()
        all_ids = [s["session_id"] for s in all_list]
        self.assertIn(session_id, all_ids)

        # 7. Unarchive the agent
        unarchive_res = self.client.post(f"/api/agents/{session_id}/unarchive")
        self.assertEqual(unarchive_res.status_code, 200)

        restored_res = self.client.get(f"/api/agents/{session_id}").json()
        self.assertFalse(restored_res["is_archived"])
        self.assertIsNone(restored_res["archived_at"])

        # 8. Verify restored in active list
        active_list_restored = self.client.get("/api/agents?include_archived=false").json()
        self.assertIn(session_id, [s["session_id"] for s in active_list_restored])

        # 9. Clean up with delete endpoint
        del_res = self.client.delete(f"/api/agents/{session_id}")
        self.assertEqual(del_res.status_code, 200)
        get_deleted = self.client.get(f"/api/agents/{session_id}")
        self.assertEqual(get_deleted.status_code, 404)

if __name__ == "__main__":
    unittest.main()
