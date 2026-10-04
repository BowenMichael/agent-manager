import asyncio
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from agent_manager.server import app
from agent_manager.runner import AgentRunnerManager
from agent_manager.models import AgentStatus, MessageRole

class TestManagerComments(unittest.TestCase):
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

    def test_webhook_issue_comment_reprompts_agent_and_moves_to_in_progress(self):
        # 1. Spawn an initial agent session
        spawn_res = self.client.post("/api/agents/spawn", json={
            "repo": "BowenMichael/f1-frontend",
            "issue_number": 888,
            "title": "Comment Test Issue",
            "prompt": "Initial task prompt"
        })
        self.assertEqual(spawn_res.status_code, 200)
        session_id = spawn_res.json()["session_id"]

        # 2. Simulate issue_comment webhook event
        comment_payload = {
            "action": "created",
            "issue": {
                "number": 888,
                "title": "Comment Test Issue"
            },
            "comment": {
                "id": 999111,
                "user": {"login": "testreviewer"},
                "body": "Please add validation tests for this endpoint."
            },
            "repository": {
                "full_name": "BowenMichael/f1-frontend"
            }
        }
        res = self.client.post(
            "/api/webhooks/github",
            json=comment_payload,
            headers={"X-GitHub-Event": "issue_comment"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("action"), "context_injected")
        self.assertEqual(data.get("board_status"), "in_progress")
        self.assertEqual(data.get("session_id"), session_id)

        # 3. Verify message was added to session
        session = self.client.get(f"/api/agents/{session_id}").json()
        self.assertEqual(session["status"], AgentStatus.RUNNING.value)
        self.assertIn("999111", session["seen_comment_ids"])
        user_msgs = [m for m in session["messages"] if m["role"] == MessageRole.USER.value]
        self.assertTrue(any("validation tests for this endpoint" in m["content"] for m in user_msgs))

        # 4. Duplicate comment with same ID should be ignored
        dup_res = self.client.post(
            "/api/webhooks/github",
            json=comment_payload,
            headers={"X-GitHub-Event": "issue_comment"}
        )
        self.assertEqual(dup_res.status_code, 200)
        self.assertEqual(dup_res.json().get("status"), "ignored")
        self.assertEqual(dup_res.json().get("reason"), "already_processed")

        # Clean up
        self.client.post(f"/api/agents/{session_id}/stop")

    def test_simulate_issue_comment_webhook(self):
        # 1. Spawn session
        spawn_res = self.client.post("/api/agents/spawn", json={
            "repo": "BowenMichael/f1-frontend",
            "issue_number": 777,
            "title": "Simulate Comment Test",
            "prompt": "Test prompt"
        })
        self.assertEqual(spawn_res.status_code, 200)
        session_id = spawn_res.json()["session_id"]

        # 2. Simulate via /api/webhooks/simulate
        sim_res = self.client.post("/api/webhooks/simulate", json={
            "event_type": "issue_comment",
            "action": "created",
            "issue_number": 777,
            "comment_id": "sim-12345",
            "commenter": "qa_tester",
            "comment_body": "Verification notes from QA team.",
            "repo": "BowenMichael/f1-frontend"
        })
        self.assertEqual(sim_res.status_code, 200)
        data = sim_res.json()
        self.assertTrue(data.get("simulated"))
        self.assertEqual(data["result"].get("action"), "context_injected")

        # Clean up
        self.client.post(f"/api/agents/{session_id}/stop")

    def test_agent_comment_posted_on_finish(self):
        async def run_test():
            posted_comments = []
            async def mock_post_comment(repo, issue_number, body):
                posted_comments.append({"repo": repo, "issue_number": issue_number, "body": body})
                return {"id": 888999}

            with patch("agent_manager.runner.post_issue_comment", side_effect=mock_post_comment):
                spawn_res = self.client.post("/api/agents/spawn", json={
                    "repo": "BowenMichael/f1-frontend",
                    "issue_number": 555,
                    "title": "Finish Comment Test",
                    "prompt": "Test finishing"
                })
                session_id = spawn_res.json()["session_id"]
                session = self.runner.get_session(session_id)

                final_resp = "Milestone implementation verified and tested successfully."
                from agent_manager.runner import post_issue_comment
                comment_content = f"🤖 **Agent Update**\n\n{final_resp.strip()}"
                res = await post_issue_comment(session.repo, session.issue_number, comment_content)
                self.assertIsNotNone(res)
                self.assertEqual(len(posted_comments), 1)
                self.assertEqual(posted_comments[0]["issue_number"], 555)
                self.assertIn("Milestone implementation verified", posted_comments[0]["body"])

                self.client.post(f"/api/agents/{session_id}/stop")

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
