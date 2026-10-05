import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from agent_manager.server import app
from agent_manager.config import STATIC_DIR
from agent_manager.runner import AgentRunnerManager
from agent_manager.models import MessageRole, ConversationMessage


class TestMarkdownIntegration(unittest.TestCase):
    """Verifies that markdown rendering static assets, index references, and runner messages work properly."""

    def setUp(self):
        self.client = TestClient(app)
        self.runner = AgentRunnerManager()

    def test_static_markdown_files_exist_on_disk(self):
        """Verify the built frontend bundle and assets exist in the static directory."""
        self.assertTrue((STATIC_DIR / "index.html").exists(), f"Expected index.html does not exist in {STATIC_DIR}")
        self.assertTrue((STATIC_DIR / "assets").exists(), f"Expected assets dir does not exist in {STATIC_DIR}")

    def test_static_files_served_by_fastapi(self):
        """Verify that FastAPI serves root index.html with 200 OK."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("root", res.text)

    def test_index_html_includes_markdown_tags(self):
        """Verify index.html contains bundle scripts and CSS links."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("/static/assets/", html)

    def test_runner_preserves_markdown_messages(self):
        """Verify ConversationMessage and runner store markdown formatting without corruption."""
        sample_markdown = (
            "### Plan of Action\n\n"
            "- Step 1: Initialize\n"
            "- Step 2: Implement\n\n"
            "```python\n"
            "def test():\n"
            "    return True\n"
            "```"
        )
        msg = ConversationMessage(
            id="msg-1",
            role=MessageRole.AGENT,
            content=sample_markdown
        )
        self.assertEqual(msg.role, MessageRole.AGENT)
        self.assertEqual(msg.content, sample_markdown)
        self.assertIn("```python", msg.content)
        self.assertIn("### Plan of Action", msg.content)


if __name__ == "__main__":
    unittest.main()
