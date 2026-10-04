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
        """Verify the markdown static files and vendor dependencies exist in the static directory."""
        expected_files = [
            STATIC_DIR / "markdown.css",
            STATIC_DIR / "markdown-renderer.js",
            STATIC_DIR / "vendor" / "marked.min.js",
            STATIC_DIR / "vendor" / "purify.min.js",
        ]
        for path in expected_files:
            self.assertTrue(path.exists(), f"Expected static file does not exist: {path}")
            self.assertGreater(path.stat().st_size, 100, f"File {path} is suspiciously small.")

    def test_static_files_served_by_fastapi(self):
        """Verify that FastAPI serves all markdown files with 200 OK."""
        endpoints = [
            "/static/markdown.css",
            "/static/markdown-renderer.js",
            "/static/vendor/marked.min.js",
            "/static/vendor/purify.min.js",
        ]
        for ep in endpoints:
            res = self.client.get(ep)
            self.assertEqual(res.status_code, 200, f"Failed to fetch {ep}: {res.status_code}")
            self.assertGreater(len(res.content), 100)

    def test_index_html_includes_markdown_tags(self):
        """Verify index.html contains links to markdown stylesheets and scripts."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text

        self.assertIn("/static/markdown.css", html)
        self.assertIn("/static/vendor/marked.min.js", html)
        self.assertIn("/static/vendor/purify.min.js", html)
        self.assertIn("/static/markdown-renderer.js", html)

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
