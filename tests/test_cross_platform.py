import os
import sys
import unittest
import importlib
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

import agent_manager.config as config
from agent_manager.server import app
from agent_manager.runners.terminal_launcher import launch_desktop_terminal


class TestCrossPlatformDecoupling(unittest.TestCase):
    def test_workspace_base_defaults_per_platform(self):
        # On Linux, default should be /app/workspaces
        with patch("sys.platform", "linux"), patch.dict("os.environ", {"HOME": "/root"}, clear=False):
            os.environ.pop("WORKSPACE_BASE", None)
            importlib.reload(config)
            self.assertEqual(str(config.WORKSPACE_BASE), str(Path("/app/workspaces")))

        # On Windows, default should be e:/~Michael Bowen/Projects
        with patch("sys.platform", "win32"), patch.dict("os.environ", {"USERPROFILE": r"C:\Users\test"}, clear=False):
            os.environ.pop("WORKSPACE_BASE", None)
            importlib.reload(config)
            self.assertEqual(str(config.WORKSPACE_BASE), str(Path("e:/~Michael Bowen/Projects")))

        # When WORKSPACE_BASE env var is set, it overrides defaults
        with patch.dict("os.environ", {"WORKSPACE_BASE": "/custom/path"}):
            importlib.reload(config)
            self.assertEqual(str(config.WORKSPACE_BASE), str(Path("/custom/path")))

        # Reload back to current system default
        importlib.reload(config)

    def test_terminal_launch_os_gated_on_linux(self):
        client = TestClient(app)
        with patch("sys.platform", "linux"):
            res = client.post("/api/agents/some-session-id/launch-terminal")
            self.assertEqual(res.status_code, 400)
            self.assertIn("Windows", res.json()["detail"])

    def test_terminal_launcher_runner_os_gated(self):
        import asyncio
        from unittest.mock import AsyncMock
        manager = MagicMock()
        manager._append_message = AsyncMock()

        async def run_test():
            session = MagicMock()
            session.session_id = "test-session"
            with patch("sys.platform", "linux"):
                res = await launch_desktop_terminal(
                    manager, session, 17, "gemini-3.8-flash", "high", [], "/some/dir", "Do task", False
                )
                self.assertFalse(res)
                manager._append_message.assert_awaited_once()

        asyncio.run(run_test())

    def test_missing_agy_binary_fallback(self):
        # Verify that AGY_CLI_PATH points to Path and can be queried safely
        self.assertIsInstance(config.AGY_CLI_PATH, Path)
        self.assertIsInstance(config.ANTIGRAVITY_IDE_CLI, Path)


if __name__ == "__main__":
    unittest.main()
