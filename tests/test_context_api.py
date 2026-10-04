import unittest
import tempfile
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from agent_manager.server import app
from agent_manager.models import AgentSessionInfo, AgentStatus
from agent_manager.runner import AgentRunnerManager


class TestContextAndTabsAPI(unittest.TestCase):
    def setUp(self):
        self.runner = AgentRunnerManager()
        self.client = TestClient(app)
        self.test_dir = tempfile.mkdtemp(prefix="test_context_wt_")

        # Initialize test git repo in temp worktree
        subprocess.run(["git", "init"], cwd=self.test_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "config", "user.name", "Test Agent"], cwd=self.test_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "config", "user.email", "agent@test.local"], cwd=self.test_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        test_file = Path(self.test_dir) / "README.md"
        test_file.write_text("# Test Repo\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.test_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "commit", "-m", "initial test commit"], cwd=self.test_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        self.session_id = "test-session-issue-1"
        self.session = AgentSessionInfo(
            session_id=self.session_id,
            title="Issue 1 Agent Tabs Test",
            repo="BowenMichael/agent-manager",
            issue_number=1,
            git_branch="feat/issue-1",
            status=AgentStatus.RUNNING,
            worktree_path=self.test_dir
        )
        self.runner.sessions[self.session_id] = self.session

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        if self.session_id in self.runner.sessions:
            del self.runner.sessions[self.session_id]

    def test_git_tree_endpoint(self):
        resp = self.client.get(f"/api/agents/{self.session_id}/git-tree")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["session_id"], self.session_id)
        self.assertEqual(data["branch"], "feat/issue-1")
        self.assertIn("initial test commit", data["git_tree"])

    @patch("agent_manager.api.context.get_issue", new_callable=AsyncMock)
    @patch("agent_manager.api.context.get_issue_comments", new_callable=AsyncMock)
    def test_issue_context_endpoint(self, mock_comments, mock_issue):
        mock_issue.return_value = {
            "number": 1,
            "title": "[TASK]: Agent tabs",
            "state": "open",
            "body": "Test requirements for tabs",
            "user": {"login": "BowenMichael"}
        }
        mock_comments.return_value = [
            {
                "id": 101,
                "user": {"login": "agent-bot"},
                "body": "Starting implementation",
                "created_at": "2026-10-04T00:00:00Z"
            }
        ]

        resp = self.client.get(f"/api/agents/{self.session_id}/issue")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["session_id"], self.session_id)
        self.assertEqual(data["repo"], "BowenMichael/agent-manager")
        self.assertEqual(data["issue_number"], 1)
        self.assertIsNotNone(data["issue"])
        self.assertEqual(data["issue"]["title"], "[TASK]: Agent tabs")
        self.assertEqual(len(data["comments"]), 1)
        self.assertEqual(data["comments"][0]["body"], "Starting implementation")


if __name__ == "__main__":
    unittest.main()
