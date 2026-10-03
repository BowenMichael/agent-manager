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

if __name__ == "__main__":
    unittest.main()
