import asyncio
import logging
import httpx
from typing import Optional, Set, Dict

from agent_manager.config import (
    GITHUB_PERSONAL_ACCESS_TOKEN, PROJECT_BOARD_ID, PROJECT_BOARD_IDS,
    DEFAULT_REPO, POLL_INTERVAL_SECONDS
)
from agent_manager.models import AgentStatus
from agent_manager.runner import AgentRunnerManager
from agent_manager.poller.constants import STATUS_NAMES
from agent_manager.poller.github_client import GitHubBoardClient
from agent_manager.poller.synchronizer import (
    handle_closed_or_done,
    handle_active_session_comments,
    handle_ready_status
)

logger = logging.getLogger("agent_manager.poller.watcher")

BOARD_QUERY = """
query($projectId: ID!) {
  node(id: $projectId) {
    ... on ProjectV2 {
      items(first: 30) {
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

    @property
    def _board_fields(self):
        return self.client._board_fields

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Local Git Watcher started (background polling every %ds)", POLL_INTERVAL_SECONDS)

    def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Local Git Watcher stopped")

    async def _poll_loop(self):
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

    async def _resolve_board_fields(self, project_id: str) -> Optional[dict]:
        return await self.client.resolve_board_fields(project_id)

    async def update_item_status(self, item_id: str, status_key: str, project_id: Optional[str] = None) -> bool:
        pid = project_id or self.item_project_map.get(item_id, PROJECT_BOARD_ID)
        return await self.client.update_item_status(item_id, status_key, pid)

    async def update_issue_status(self, repo: str, issue_number: int, status_key: str) -> bool:
        key = f"{repo}#{issue_number}"
        item_id = self.item_id_map.get(key)
        if not item_id:
            for b in PROJECT_BOARD_IDS:
                await self._check_project_board(b)
                if key in self.item_id_map:
                    item_id = self.item_id_map[key]
                    break
        if item_id:
            return await self.update_item_status(item_id, status_key)
        logger.warning("Could not find project board item for %s", key)
        return False

    async def _check_project_board(self, project_id: str = PROJECT_BOARD_ID):
        headers = {
            "Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "AgentManagerLocal/1.0"
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.github.com/graphql",
                json={"query": BOARD_QUERY, "variables": {"projectId": project_id}},
                headers=headers
            )
            if resp.status_code != 200:
                logger.warning("GraphQL request failed with status: %s", resp.status_code)
                return

            data = resp.json()
            items = data.get("data", {}).get("node", {}).get("items", {}).get("nodes", [])

            for item in items:
                status_name = None
                for fv in item.get("fieldValues", {}).get("nodes", []):
                    if fv.get("field", {}).get("name") == "Status":
                        status_name = fv.get("name")
                        break

                content = item.get("content")
                if not content or "number" not in content:
                    continue

                issue_num = content["number"]
                title = content["title"]
                body = content.get("body") or ""
                issue_state = content.get("state", "OPEN")
                repo = content.get("repository", {}).get("nameWithOwner", DEFAULT_REPO)
                comments = content.get("comments", {}).get("nodes", [])
                issue_key = f"{repo}#{issue_num}"
                self.item_id_map[issue_key] = item["id"]
                self.item_project_map[item["id"]] = project_id

                if issue_state == "CLOSED" or status_name == STATUS_NAMES["done"]:
                    await handle_closed_or_done(self, item["id"], issue_num, repo, issue_state, status_name, issue_key)
                    continue

                active_session = next(
                    (s for s in reversed(self.runner.list_sessions()) if s.issue_number == issue_num and s.repo == repo and s.status != AgentStatus.COMPLETED),
                    None
                )

                if active_session:
                    comment_injected = await handle_active_session_comments(
                        self, active_session, item["id"], issue_num, repo, body, comments, status_name
                    )
                    if comment_injected:
                        continue

                if active_session and active_session.status == AgentStatus.IN_REVIEW:
                    if status_name != STATUS_NAMES["in_review"]:
                        await self.update_item_status(item["id"], "in_review")
                        logger.info("Updated Issue #%s Project Board status to '🔍 In Review'", issue_num)

                if status_name == STATUS_NAMES["ready"]:
                    await handle_ready_status(self, active_session, item["id"], issue_num, repo, title, body, comments, issue_key)
