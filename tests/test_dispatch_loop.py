import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from agent_manager.models import AgentSessionInfo, AgentStatus
from agent_manager.cron.scheduler import ProjectBacklogDispatcher
from agent_manager.services.dispatch_trigger import fire_dispatch_hook


class TestDispatchLoop(unittest.TestCase):
    def setUp(self):
        # Reset singleton instance between tests
        ProjectBacklogDispatcher._instance = None
        self.dispatcher = ProjectBacklogDispatcher()

    @patch("agent_manager.cron.scheduler.check_and_update_agent_manager")
    @patch("agent_manager.cron.scheduler.fetch_board_items")
    @patch("agent_manager.cron.scheduler.promote_backlog_issue")
    def test_check_and_dispatch_skips_when_agents_running(
        self, mock_promote, mock_fetch, mock_update
    ):
        async def run_test():
            mock_runner = MagicMock()
            session = AgentSessionInfo(
                session_id="test-session-1",
                title="Test Issue Title",
                repo="BowenMichael/agent-manager",
                issue_number=48,
                status=AgentStatus.RUNNING,
            )
            mock_runner.list_sessions.return_value = [session]
            mock_runner._active_agents = {}

            with patch("agent_manager.runner.AgentRunnerManager", return_value=mock_runner):
                result = await self.dispatcher.check_and_dispatch()

                self.assertEqual(result["status"], "agents_running")
                self.assertIn("Local active agent(s) detected", result["message"])
                self.assertEqual(result["active_agent_count"], 1)
                # Verify that board fetch, promotion, and updates are skipped
                mock_update.assert_not_called()
                mock_fetch.assert_not_called()
                mock_promote.assert_not_called()

        asyncio.run(run_test())

    @patch("agent_manager.cron.scheduler.check_and_update_agent_manager")
    @patch("agent_manager.cron.scheduler.fetch_board_items")
    @patch("agent_manager.cron.scheduler.promote_backlog_issue")
    def test_check_and_dispatch_skips_when_active_board_items_present(
        self, mock_promote, mock_fetch, mock_update
    ):
        async def run_test():
            mock_runner = MagicMock()
            mock_runner.list_sessions.return_value = []
            mock_runner._active_agents = {}

            mock_update.return_value = {"checked": True, "updated": False}
            active_item = {
                "item_id": "item-1",
                "project_id": "proj-1",
                "board_title": "Project Board",
                "issue_number": 48,
                "title": "In Progress Issue",
                "status": "In Progress",
            }
            backlog_item = {
                "item_id": "item-2",
                "project_id": "proj-1",
                "board_title": "Project Board",
                "issue_number": 49,
                "title": "Next Backlog Task",
                "status": "Backlog",
            }
            mock_fetch.return_value = ([active_item], [backlog_item])

            with patch("agent_manager.runner.AgentRunnerManager", return_value=mock_runner), \
                 patch("agent_manager.cron.scheduler.GITHUB_PERSONAL_ACCESS_TOKEN", "mock_token"):
                result = await self.dispatcher.check_and_dispatch()

                self.assertEqual(result["status"], "active_issue_present")
                self.assertEqual(result["active_count"], 1)
                mock_promote.assert_not_called()

        asyncio.run(run_test())

    @patch("agent_manager.cron.scheduler.check_and_update_agent_manager")
    @patch("agent_manager.cron.scheduler.fetch_board_items")
    @patch("agent_manager.cron.scheduler.promote_backlog_issue")
    def test_check_and_dispatch_promotes_backlog_when_idle(
        self, mock_promote, mock_fetch, mock_update
    ):
        async def run_test():
            mock_runner = MagicMock()
            mock_runner.list_sessions.return_value = []
            mock_runner._active_agents = {}

            mock_update.return_value = {"checked": True, "updated": False}
            backlog_item = {
                "item_id": "item-100",
                "project_id": "proj-1",
                "board_title": "Project Board",
                "issue_number": 50,
                "title": "Autonomous Feature",
                "status": "Backlog",
            }
            mock_fetch.return_value = ([], [backlog_item])
            mock_promote.return_value = (True, "Promoted Issue #50 to Ready for Agent")

            with patch("agent_manager.runner.AgentRunnerManager", return_value=mock_runner), \
                 patch("agent_manager.cron.scheduler.GITHUB_PERSONAL_ACCESS_TOKEN", "mock_token"):
                result = await self.dispatcher.check_and_dispatch()

                self.assertEqual(result["status"], "dispatched")
                self.assertIn("Promoted Issue #50", result["message"])
                self.assertEqual(result["promoted_issue"]["issue_number"], 50)
                mock_promote.assert_called_once()

        asyncio.run(run_test())

    @patch("agent_manager.cron.scheduler.check_and_update_agent_manager")
    @patch("agent_manager.cron.scheduler.fetch_board_items")
    @patch("agent_manager.cron.scheduler.promote_backlog_issue")
    def test_check_and_dispatch_skips_when_in_review_board_item_present(
        self, mock_promote, mock_fetch, mock_update
    ):
        async def run_test():
            mock_runner = MagicMock()
            mock_runner.list_sessions.return_value = []
            mock_runner._active_agents = {}

            mock_update.return_value = {"checked": True, "updated": False}
            active_item = {
                "item_id": "item-in-review",
                "project_id": "proj-1",
                "board_title": "Project Board",
                "issue_number": 47,
                "title": "In Review Task",
                "status": "🔍 In Review",
            }
            backlog_item = {
                "item_id": "item-2",
                "project_id": "proj-1",
                "board_title": "Project Board",
                "issue_number": 49,
                "title": "Next Backlog Task",
                "status": "Backlog",
            }
            mock_fetch.return_value = ([active_item], [backlog_item])

            with patch("agent_manager.runner.AgentRunnerManager", return_value=mock_runner), \
                 patch("agent_manager.cron.scheduler.GITHUB_PERSONAL_ACCESS_TOKEN", "mock_token"):
                result = await self.dispatcher.check_and_dispatch()

                self.assertEqual(result["status"], "active_issue_present")
                self.assertEqual(result["active_count"], 1)
                mock_promote.assert_not_called()

        asyncio.run(run_test())

    def test_trigger_dispatch_now_and_fire_hook(self):
        async def run_test():
            with patch.object(self.dispatcher, "check_and_dispatch", new_callable=AsyncMock) as mock_dispatch:
                mock_dispatch.return_value = {"status": "ok"}
                await self.dispatcher.trigger_dispatch_now(delay_seconds=0)
                mock_dispatch.assert_called_once()

        asyncio.run(run_test())

    def test_fire_dispatch_hook_spawns_task(self):
        async def run_test():
            with patch.object(ProjectBacklogDispatcher, "trigger_dispatch_now", new_callable=AsyncMock) as mock_trigger:
                task = fire_dispatch_hook(delay_seconds=0)
                self.assertIsNotNone(task)
                await task
                mock_trigger.assert_called_once_with(delay_seconds=0)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
