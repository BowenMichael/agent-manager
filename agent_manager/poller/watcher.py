"""
Local Git Project Board Watcher.
Periodically polls GitHub GraphQL boards, tracks card states, and triggers orchestrations.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import asyncio
import logging
from typing import Optional, Set, Dict

from agent_manager.config import (
    GITHUB_PERSONAL_ACCESS_TOKEN, PROJECT_BOARD_ID, PROJECT_BOARD_IDS,
    DEFAULT_REPO, POLL_INTERVAL_SECONDS
)
from agent_manager.models import AgentStatus
from agent_manager.runner import AgentRunnerManager
from agent_manager.poller.constants import STATUS_NAMES
from agent_manager.poller.github_client import GitHubBoardClient, execute_graphql_with_retry
from agent_manager.poller.synchronizer import (
    handle_closed_or_done,
    handle_active_session_comments,
    handle_ready_status,
    broadcast_board_sync
)

logger = logging.getLogger("agent_manager.poller.watcher")

BOARD_QUERY = """
query($projectId: ID!) {
  node(id: $projectId) {
    ... on ProjectV2 {
      items(first: 100) {
        nodes {
          id
          fieldValues(first: 10) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                optionId
                field { ... on ProjectV2SingleSelectField { name } }
              }
            }
          }
          content {
            ... on Issue {
              id
              number
              title
              body
              state
              updatedAt
              comments(last: 10) {
                nodes {
                  id
                  author { login }
                  body
                  createdAt
                }
              }
              repository { nameWithOwner }
            }
          }
        }
      }
    }
  }
}
"""


class LocalGitWatcher:
    _instance: Optional["LocalGitWatcher"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_watcher()
        return cls._instance

    def _init_watcher(self):
        self.runner = AgentRunnerManager()
        self.client = GitHubBoardClient()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.active_issues: Set[str] = set()
        self.item_id_map: Dict[str, str] = {}
        self.item_project_map: Dict[str, str] = {}

    def start(self):
        """Starts the background poller loop task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Local Git Watcher started (polling every %ds)", POLL_INTERVAL_SECONDS)

    def stop(self):
        """Stops the background poller task cleanly."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Local Git Watcher stopped")

    async def _poll_loop(self):
        """Main periodic polling loop checking all configured project boards."""
        while self._running:
            try:
                if GITHUB_PERSONAL_ACCESS_TOKEN:
                    for board_id in PROJECT_BOARD_IDS:
                        await self._check_project_board(board_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in Git watcher poll: %s", e)
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def update_item_status(self, item_id: str, status_key: str, project_id: Optional[str] = None) -> bool:
        """Mutates item status on GitHub Project Board."""
        pid = project_id or self.item_project_map.get(item_id, PROJECT_BOARD_ID)
        return await self.client.update_item_status(item_id, status_key, pid)

    async def update_issue_status(self, repo: str, issue_number: int, status_key: str) -> bool:
        """Finds item ID by repo and issue number and updates status."""
        keys = [f"{repo}#{issue_number}".lower(), f"{repo.split('/')[-1]}#{issue_number}".lower(), str(issue_number)]
        item_id = next((self.item_id_map.get(k) for k in keys if self.item_id_map.get(k)), None)
        if not item_id:
            for b in PROJECT_BOARD_IDS:
                await self._check_project_board(b)
                item_id = next((self.item_id_map.get(k) for k in keys if self.item_id_map.get(k)), None)
                if item_id:
                    break
        success = await self.update_item_status(item_id, status_key) if item_id else False
        if success:
            await broadcast_board_sync(self, issue_number, repo, status_key)
        return success

    def _extract_item_status(self, item: dict) -> Optional[str]:
        """Extracts status option name from ProjectV2 item field values."""
        for fv in item.get("fieldValues", {}).get("nodes", []):
            if fv.get("field", {}).get("name") == "Status":
                return fv.get("name")
        return None

    async def _process_board_item(self, item: dict, project_id: str):
        """Processes single board item, routes to status handler, and records IDs."""
        content = item.get("content")
        if not content or "number" not in content:
            return

        status_name = self._extract_item_status(item)
        num = content["number"]
        repo = (content.get("repository") or {}).get("nameWithOwner", DEFAULT_REPO)
        issue_key = f"{repo}#{num}"

        self.item_id_map[issue_key.lower()] = item["id"]
        self.item_project_map[item["id"]] = project_id

        if content.get("state") == "CLOSED" or status_name == STATUS_NAMES["done"]:
            await handle_closed_or_done(self, item["id"], num, repo, content.get("state", "OPEN"), status_name, issue_key)
            return

        active = next((s for s in reversed(self.runner.list_sessions()) if s.issue_number == num and s.repo == repo and s.status != AgentStatus.COMPLETED), None)
        if active and await handle_active_session_comments(self, active, item["id"], num, repo, content.get("body") or "", content.get("comments", {}).get("nodes", []), status_name):
            return

        if active and active.status == AgentStatus.IN_REVIEW and status_name != STATUS_NAMES["in_review"]:
            await self.update_item_status(item["id"], "in_review")
            await broadcast_board_sync(self, num, repo, "in_review")

        if status_name == STATUS_NAMES["ready"]:
            await handle_ready_status(self, active, item["id"], num, repo, content.get("title", ""), content.get("body") or "", content.get("comments", {}).get("nodes", []), issue_key)

    async def _check_project_board(self, project_id: str = PROJECT_BOARD_ID):
        """Fetches board items using GraphQL client with retry and processes them."""
        data = await execute_graphql_with_retry(BOARD_QUERY, {"projectId": project_id})
        if not data:
            return

        items = data.get("data", {}).get("node", {}).get("items", {}).get("nodes", [])
        for item in items:
            try:
                await self._process_board_item(item, project_id)
            except Exception as e:
                logger.error("Error processing board item %s: %s", item.get("id"), e)
