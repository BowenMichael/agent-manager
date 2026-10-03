import asyncio
import unittest
from fastapi.testclient import TestClient

from agent_manager.server import app
from agent_manager.runner import AgentRunnerManager
from agent_manager.models import AgentStatus, MessageRole

class TestAgentManager(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.runner = AgentRunnerManager()
        async def mock_run_agent_loop(session_id, prompt, worktree, is_continuation=False):
            return
        self.original_run_loop = self.runner._run_agent_loop
        self.runner._run_agent_loop = mock_run_agent_loop

    def tearDown(self):
        self.runner._run_agent_loop = self.original_run_loop

    def test_webhook_issues_ready_trigger(self):
        payload = {
            "action": "labeled",
            "issue": {
                "number": 101,
                "title": "Test Issue for Agent Manager",
                "body": "Automated test description",
                "labels": [{"name": "agent:ready"}]
            },
            "repository": {
                "full_name": "BowenMichael/f1-frontend"
            }
        }
        res = self.client.post(
            "/api/webhooks/github",
            json=payload,
            headers={"X-GitHub-Event": "issues"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("action"), "agent_spawned")
        self.assertIn("session_id", data)

    def test_webhook_ignored_when_not_ready(self):
        payload = {
            "action": "labeled",
            "issue": {
                "number": 102,
                "title": "Unrelated issue",
                "labels": [{"name": "documentation"}]
            }
        }
        res = self.client.post(
            "/api/webhooks/github",
            json=payload,
            headers={"X-GitHub-Event": "issues"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), "ignored")

    def test_agent_lifecycle_api(self):
        # 1. Spawn Agent
        spawn_res = self.client.post("/api/agents/spawn", json={
            "repo": "BowenMichael/f1-frontend",
            "issue_number": 999,
            "title": "Lifecycle Test Issue",
            "prompt": "Test execution prompt"
        })
        self.assertEqual(spawn_res.status_code, 200)
        session = spawn_res.json()
        session_id = session["session_id"]
        self.assertIn(session["status"], [AgentStatus.INITIALIZING.value, AgentStatus.RUNNING.value])

        # 2. Add Context
        ctx_res = self.client.post(f"/api/agents/{session_id}/context", json={
            "context": "Here is additional context from pairing session."
        })
        self.assertEqual(ctx_res.status_code, 200)

        # 3. Stop Agent
        stop_res = self.client.post(f"/api/agents/{session_id}/stop", json={
            "reason": "Test finished"
        })
        self.assertEqual(stop_res.status_code, 200)

        # 4. Verify Final Status
        get_res = self.client.get(f"/api/agents/{session_id}")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["status"], AgentStatus.STOPPED.value)

    def test_settings_model_effort_and_next_prompt_update(self):
        # 1. Update settings with new model, effort, and overage credits
        settings_res = self.client.post("/api/settings", json={
            "default_model": "claude-sonnet-5-5",
            "default_effort": "medium",
            "allow_overage_credits": True,
            "max_session_tokens": 120000
        })
        self.assertEqual(settings_res.status_code, 200)
        data = settings_res.json()
        self.assertEqual(data["default_model"], "claude-sonnet-5-5")
        self.assertEqual(data["default_effort"], "medium")
        self.assertTrue(data["allow_overage_credits"])

        # 2. Verify GET /api/settings
        get_settings_res = self.client.get("/api/settings")
        self.assertEqual(get_settings_res.status_code, 200)
        curr_settings = get_settings_res.json()
        self.assertEqual(curr_settings["default_model"], "claude-sonnet-5-5")
        self.assertEqual(curr_settings["default_effort"], "medium")
        self.assertTrue(curr_settings["allow_overage_credits"])

        # 3. Spawn agent and verify model and effort
        spawn_res = self.client.post("/api/agents/spawn", json={
            "issue_number": 998,
            "title": "Model Effort Test Agent",
            "prompt": "Initial prompt"
        })
        self.assertEqual(spawn_res.status_code, 200)
        session = spawn_res.json()
        session_id = session["session_id"]
        self.assertEqual(session.get("model"), "claude-sonnet-5-5")
        self.assertEqual(session.get("effort"), "medium")

        # 4. Change settings to another model and effort
        self.client.post("/api/settings", json={
            "default_model": "gemini-3.8-flash",
            "default_effort": "low"
        })

        # 5. Prompt the agent again (add_context)
        ctx_res = self.client.post(f"/api/agents/{session_id}/context", json={
            "context": "Follow-up instruction for agent"
        })
        self.assertEqual(ctx_res.status_code, 200)

        # 6. Verify session updated to the new model and effort for this next prompt
        updated_session = self.client.get(f"/api/agents/{session_id}").json()
        self.assertEqual(updated_session.get("model"), "gemini-3.8-flash")
        self.assertEqual(updated_session.get("effort"), "low")

        # Clean up
        self.client.post(f"/api/agents/{session_id}/stop")

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
