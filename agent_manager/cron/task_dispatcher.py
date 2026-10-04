import logging
from typing import Dict, Any, List
import httpx
from agent_manager.config import GITHUB_PERSONAL_ACCESS_TOKEN, PROJECT_BOARD_IDS

logger = logging.getLogger("agent_manager.cron.task_dispatcher")

GRAPHQL_QUERY = """
query($projectId: ID!) {
  node(id: $projectId) {
    ... on ProjectV2 {
      title
      items(first: 50) {
        nodes {
          id
          fieldValues(first: 10) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                optionId
                field { ... on ProjectV2SingleSelectField { name id } }
              }
            }
          }
          content {
            ... on Issue {
              number
              title
              repository { nameWithOwner }
            }
          }
        }
      }
    }
  }
}
"""


async def fetch_board_items() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Fetches items from configured GitHub Project Boards and categorizes
    them into active_items and backlog_items.
    """
    if not GITHUB_PERSONAL_ACCESS_TOKEN:
        logger.warning("[Cron Dispatcher] No GitHub Personal Access Token configured. Skipping.")
        return [], []

    headers = {
        "Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "AgentManagerCron/1.0"
    }

    active_items = []
    backlog_items = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        for bid in PROJECT_BOARD_IDS:
            resp = await client.post(
                "https://api.github.com/graphql",
                json={"query": GRAPHQL_QUERY, "variables": {"projectId": bid}},
                headers=headers
            )
            if resp.status_code != 200:
                logger.warning("[Cron Dispatcher] GraphQL query failed for board %s: %s", bid, resp.status_code)
                continue

            node = resp.json().get("data", {}).get("node", {}) or {}
            board_title = node.get("title", bid)
            for item in node.get("items", {}).get("nodes", []):
                content = item.get("content") or {}
                status_name = None
                for fv in item.get("fieldValues", {}).get("nodes", []):
                    if fv.get("field", {}).get("name") == "Status":
                        status_name = fv.get("name")
                        break

                if not status_name or not content.get("number"):
                    continue

                item_data = {
                    "item_id": item["id"],
                    "project_id": bid,
                    "board_title": board_title,
                    "issue_number": content.get("number"),
                    "title": content.get("title"),
                    "repo": (content.get("repository") or {}).get("nameWithOwner"),
                    "status": status_name
                }

                if "In Progress" in status_name or "Ready for Agent" in status_name:
                    active_items.append(item_data)
                elif "Backlog" in status_name:
                    backlog_items.append(item_data)

    return active_items, backlog_items


async def promote_backlog_issue(watcher: Any, issue_item: Dict[str, Any]) -> tuple[bool, str]:
    """Promotes an issue to 'Ready for Agent' on the project board."""
    success = await watcher.update_item_status(
        issue_item["item_id"],
        "ready",
        project_id=issue_item["project_id"]
    )
    if success:
        msg = f"Promoted Issue #{issue_item['issue_number']} \"{issue_item['title']}\" from [{issue_item['board_title']}] Backlog to '📋 Ready for Agent'."
        logger.info(f"[Cron Dispatcher] 🚀 {msg}")
        return True, msg
    else:
        msg = f"Failed to update board status for Issue #{issue_item['issue_number']}."
        logger.error(f"[Cron Dispatcher] ❌ {msg}")
        return False, msg
