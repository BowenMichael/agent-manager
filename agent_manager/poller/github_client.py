"""
GitHub Board GraphQL and REST Client.
Handles project board field resolution, status mutations, and retries with backoff.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import asyncio
import logging
import random
from typing import Optional, Dict, Any
import httpx
from agent_manager.config import GITHUB_PERSONAL_ACCESS_TOKEN
from agent_manager.poller.constants import STATUS_NAMES

logger = logging.getLogger("agent_manager.poller.client")

RESOLVE_FIELDS_QUERY = """
query($projectId: ID!) {
  node(id: $projectId) {
    ... on ProjectV2 {
      fields(first: 30) {
        nodes {
          ... on ProjectV2SingleSelectField { id name options { id name } }
        }
      }
    }
  }
}
"""

UPDATE_ITEM_STATUS_MUTATION = """
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


async def execute_graphql_with_retry(query: str, variables: Dict[str, Any], max_retries: int = 3) -> Optional[Dict[str, Any]]:
    """Executes a GraphQL request with exponential backoff and jitter for rate-limit resilience."""
    headers = {
        "Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "AgentManager-Sync/1.0"
    }

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.github.com/graphql",
                    json={"query": query, "variables": variables},
                    headers=headers
                )
            if resp.status_code == 200:
                return resp.json()

            if resp.status_code in (403, 429, 500, 502, 503, 504):
                retry_after = float(resp.headers.get("retry-after", 2 ** attempt + random.uniform(0.1, 0.5)))
                logger.warning("GraphQL attempt %d failed (%d). Retrying in %.2fs", attempt, resp.status_code, retry_after)
                await asyncio.sleep(retry_after)
            else:
                logger.error("GraphQL error status %d: %s", resp.status_code, resp.text)
                return None
        except Exception as e:
            if attempt == max_retries:
                logger.error("GraphQL request failed after %d retries: %s", max_retries, e)
                return None
            await asyncio.sleep(2 ** attempt + random.uniform(0.1, 0.5))
    return None


class GitHubBoardClient:
    def __init__(self):
        self._board_fields: Dict[str, dict] = {}

    def _extract_status_field(self, nodes: list) -> Optional[dict]:
        """Parses ProjectV2 fields to extract Status field and option IDs."""
        for f in nodes:
            if f and f.get("name") == "Status":
                opts = {}
                for key, name in STATUS_NAMES.items():
                    for o in f.get("options", []):
                        if o.get("name") == name:
                            opts[key] = o.get("id")
                return {"field_id": f.get("id"), "options": opts}
        return None

    async def resolve_board_fields(self, project_id: str) -> Optional[dict]:
        """Resolves single-select Status field IDs for a ProjectV2 board."""
        if project_id in self._board_fields:
            return self._board_fields[project_id]

        data = await execute_graphql_with_retry(RESOLVE_FIELDS_QUERY, {"projectId": project_id})
        if not data:
            return None

        nodes = (data.get("data", {}).get("node", {}) or {}).get("fields", {}).get("nodes", [])
        status_info = self._extract_status_field(nodes)
        if status_info:
            self._board_fields[project_id] = status_info
            return status_info

        logger.warning("No Status field found on project %s", project_id)
        return None

    async def update_item_status(self, item_id: str, status_key: str, project_id: str) -> bool:
        """Mutates a ProjectV2 item status field with retry protection."""
        board = await self.resolve_board_fields(project_id)
        if not board or status_key not in board.get("options", {}):
            logger.warning("Cannot resolve status '%s' on project %s", status_key, project_id)
            return False

        option_id = board["options"][status_key]
        vars_payload = {
            "projectId": project_id,
            "itemId": item_id,
            "fieldId": board["field_id"],
            "optionId": option_id
        }
        res = await execute_graphql_with_retry(UPDATE_ITEM_STATUS_MUTATION, vars_payload)
        if not res or res.get("errors"):
            logger.error("Failed to mutate item status: %s", res.get("errors") if res else "No response")
            return False
        return True
