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

class LocalGitWatcher:
    """
    Local Git & Project Board Synchronizer.
    Enables 100% local agent dispatching without opening external ports or tunnels.
    """
    def __init__(self):
        self.runner = AgentRunnerManager()
        self.active_issues: Set[int] = set()
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
                      comments(last: 5) {
                        nodes {
                          body
                          author { login }
                        }
                      }
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

                # Check if moved to Ready for Agent
                if status_name == "📋 Ready for Agent":
                    # Check if already handled or running
                    active_sessions = [
                        s for s in self.runner.list_sessions()
                        if s.issue_number == issue_num and s.status in [AgentStatus.RUNNING, AgentStatus.INITIALIZING, AgentStatus.PAUSED]
                    ]
                    if not active_sessions and issue_num not in self.active_issues:
                        logger.info("Found issue #%s in Ready for Agent. Spawning autonomous agent...", issue_num)
                        self.active_issues.add(issue_num)

                        prompt = (
                            f"You have been assigned to GitHub Issue #{issue_num} in {repo}.\n\n"
                            f"**Title**: {title}\n\n"
                            f"**Requirements / Description**:\n{body}\n\n"
                            f"**Operational Guidelines**:\n"
                            f"- Work inside the designated branch and isolated worktree .worktrees/issue-{issue_num}.\n"
                            f"- Inspect existing code patterns before modifying.\n"
                            f"- Follow AGENTS.md rules and keep documentation updated.\n"
                            f"- When done, commit changes, open a pull request, and summarize your work."
                        )
                        spawn_req = SpawnRequest(
                            repo=repo,
                            issue_number=issue_num,
                            title=title,
                            prompt=prompt
                        )
                        await self.runner.spawn_agent(spawn_req)
