import os
import shutil
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from agent_manager.server import app
from agent_manager.models import AgentSessionInfo, AgentStatus
from agent_manager.runner import AgentRunnerManager
from agent_manager.utils.command_formatter import format_command_output


class TestFilesAPIAndCommandFormatter(unittest.TestCase):
    def setUp(self):
        self.runner = AgentRunnerManager()
        self.client = TestClient(app)
        self.test_dir = tempfile.mkdtemp(prefix="agy_test_wt_")

        # Create dummy file inside test worktree
        self.dummy_file = Path(self.test_dir) / "test_script.py"
        self.dummy_content = "def hello():\n    return 'world'\n"
        self.dummy_file.write_text(self.dummy_content, encoding="utf-8")

        # Create subfolder and nested file
        self.sub_dir = Path(self.test_dir) / "nested"
        self.sub_dir.mkdir()
        self.nested_file = self.sub_dir / "nested_doc.txt"
        self.nested_file.write_text("Line 1\nLine 2\nLine 3\n", encoding="utf-8")

        # Register test session
        self.session_id = "test-session-issue-43"
        self.session = AgentSessionInfo(
            session_id=self.session_id,
            title="Issue 43 File Inspection Test",
            repo="BowenMichael/agent-manager",
            status=AgentStatus.RUNNING,
            worktree_path=self.test_dir
        )
        self.runner.sessions[self.session_id] = self.session

    def tearDown(self):
        if self.session_id in self.runner.sessions:
            del self.runner.sessions[self.session_id]
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_get_file_content_success(self):
        res = self.client.get(
            f"/api/agents/{self.session_id}/files/content",
            params={"path": "test_script.py"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["filename"], "test_script.py")
        self.assertEqual(data["content"], self.dummy_content)
        self.assertEqual(data["lines"], 3)

    def test_get_nested_file_content(self):
        res = self.client.get(
            f"/api/agents/{self.session_id}/files/content",
            params={"path": "nested/nested_doc.txt"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("Line 1", data["content"])
        self.assertEqual(data["lines"], 4)

    def test_path_traversal_blocked(self):
        # Attempt to access outside directory via ../
        res = self.client.get(
            f"/api/agents/{self.session_id}/files/content",
            params={"path": "../../some_secret.txt"}
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("Access forbidden", res.json()["detail"])

    def test_file_not_found(self):
        res = self.client.get(
            f"/api/agents/{self.session_id}/files/content",
            params={"path": "non_existent.py"}
        )
        self.assertEqual(res.status_code, 404)

    def test_directory_target_rejected(self):
        res = self.client.get(
            f"/api/agents/{self.session_id}/files/content",
            params={"path": "nested"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("directory", res.json()["detail"].lower())

    def test_invalid_session(self):
        res = self.client.get(
            "/api/agents/non-existent-session/files/content",
            params={"path": "test_script.py"}
        )
        self.assertEqual(res.status_code, 404)

    def test_command_output_formatter_structured(self):
        # Test dict formatting
        raw_dict = {
            "stdout": "build success",
            "stderr": "warning: deprecation",
            "exit_code": 0
        }
        formatted = format_command_output("run_command", raw_dict)
        self.assertIn("Exit Code: 0", formatted)
        self.assertIn("[STDOUT]\nbuild success", formatted)
        self.assertIn("[STDERR]\nwarning: deprecation", formatted)

    def test_command_output_formatter_plain_and_done(self):
        # Generic 'Done' or empty
        res_done = format_command_output("run_command", "Done")
        self.assertIn("successfully", res_done)

        # Standard output
        res_plain = format_command_output("run_command", "All tests passed (12 passed)")
        self.assertEqual(res_plain, "All tests passed (12 passed)")
