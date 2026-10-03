import asyncio
import logging
import httpx
from typing import Optional, Set

from agent_manager.config import (
    GITHUB_PERSONAL_ACCESS_TOKEN, PROJECT_BOARD_ID,
    DEFAULT_REPO, POLL_INTERVAL_SECONDS
)
from agent_manager.models import SpawnRequest, AgentStatus
from agent_manager.runner import AgentRunnerManager

logger = logging.getLogger("agent_manager.poller")

# Project Board V2 Field and Option IDs (F1 Viewer Sprint Board)
STATUS_FIELD_ID = "PVTSSF_lAHOAgkA3s4BlmhhzhkSuu0"
STATUS_OPTIONS = {
    "backlog": "3abe26ce",      # 📥 Backlog
    "ready": "8b88d8d3",        # 📋 Ready for Agent
    "in_progress": "0855f60f",  # ⚡ In Progress
    "in_review": "14cfb9b7",    # 🔍 In Review
    "done": "b167c286"          # ✅ Done
}

class LocalGitWatcher:
    """
    Local Git & Project Board Synchronizer.
    Enables 100% local agent dispatching without opening external ports or tunnels.
    Moves board status directly without adding tags/labels to issues.
    """
    def __init__(self):
        self.runner = AgentRunnerManager()
        self.active_issues: Set[int] = set()
        self.item_id_map: dict[int, str] = {}  # issue_number -> project_item_id
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._poll_loop())
            logger.info("Local Git Watcher started (polling interval: %ss)", POLL_INTERVAL_SECONDS)

    def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Local Git Watcher stopped")

    async def _poll_loop(self):
        while self._running:
            try:
                if GITHUB_PERSONAL_ACCESS_TOKEN and PROJECT_BOARD_ID:
                    await self._check_project_board()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in Git watcher poll: %s", e)

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def update_item_status(self, item_id: str, option_id: str) -> bool:
        """Updates the status column directly on GitHub Project Board V2 without touching issue tags."""
        mutation = """
        mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
          updateProjectV2ItemFieldValue(
            input: {
              projectId: $projectId
              itemId: $itemId
              fieldId: $fieldId
              value: { singleSelectOptionId: $optionId }
            }
          ) {
            projectV2Item { id }
          }
        }
        """
        headers = {
            "Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "AgentManagerLocal/1.0"
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.github.com/graphql",
                json={
                    "query": mutation,
                    "variables": {
                        "projectId": PROJECT_BOARD_ID,
                        "itemId": item_id,
                        "fieldId": STATUS_FIELD_ID,
                        "optionId": option_id
                    }
                },
                headers=headers
            )
            return resp.status_code == 200

    async def _check_project_board(self):
        query = """
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
                        field { ... on ProjectV2SingleSelectField { name } }
                      }
                    }
                  }
                  content {
                    ... on Issue {
                      number
                      title
                      body
                      repository { nameWithOwner }
                    }
                  }
                }
              }
            }
          }
        }
        """
        headers = {
            "Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "AgentManagerLocal/1.0"
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.github.com/graphql",
                json={"query": query, "variables": {"projectId": PROJECT_BOARD_ID}},
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
                body = content["body"] or ""
                repo = content.get("repository", {}).get("nameWithOwner", DEFAULT_REPO)
                self.item_id_map[issue_num] = item["id"]

                # Check if moved to Ready for Agent
                if status_name == "📋 Ready for Agent":
                    active_sessions = [
                        s for s in self.runner.list_sessions()
                        if s.issue_number == issue_num and s.status in [AgentStatus.RUNNING, AgentStatus.INITIALIZING, AgentStatus.PAUSED]
                    ]
                    if not active_sessions and issue_num not in self.active_issues:
                        logger.info("Found issue #%s in Ready for Agent. Moving status to In Progress on Project Board...", issue_num)
                        self.active_issues.add(issue_num)

                        # Move Status directly on the Project Board (NOT adding issue tags/labels)
                        await self.update_item_status(item["id"], STATUS_OPTIONS["in_progress"])
                        logger.info("Updated Issue #%s Project Board status to '⚡ In Progress'", issue_num)

                        prompt = (
                            f"You have been assigned to GitHub Issue #{issue_num} in {repo}.\n\n"
                            f"**Title**: {title}\n\n"
                            f"**Requirements / Description**:\n{body}\n\n"
                            f"**Operational Guidelines**:\n"
                            f"- Work inside the designated branch and isolated worktree .worktrees/issue-{issue_num}.\n"
                            f"- Inspect existing code patterns before modifying.\n"
                            f"- Follow AGENTS.md rules and keep documentation updated.\n"
                            f"- CRITICAL RULE: Do NOT add, remove, or modify GitHub issue labels/tags. Status transitions are managed purely on the GitHub Project Board columns.\n"
                            f"- When done, commit changes, open a pull request, and summarize your work."
                        )
                        spawn_req = SpawnRequest(
                            repo=repo,
                            issue_number=issue_num,
                            title=title,
                            prompt=prompt
                        )
                        await self.runner.spawn_agent(spawn_req)
