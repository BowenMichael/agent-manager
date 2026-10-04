import logging
from typing import Optional, Dict
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


class GitHubBoardClient:
    def __init__(self):
        self._board_fields: Dict[str, dict] = {}

    async def resolve_board_fields(self, project_id: str) -> Optional[dict]:
        if project_id in self._board_fields:
            return self._board_fields[project_id]

        headers = {
            "Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "AgentManagerLocal/1.0"
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.github.com/graphql",
                json={"query": RESOLVE_FIELDS_QUERY, "variables": {"projectId": project_id}},
                headers=headers
            )
        nodes = (resp.json().get("data", {}).get("node", {}) or {}).get("fields", {}).get("nodes", [])
        for f in nodes:
            if f and f.get("name") == "Status":
                opts = {}
                for key, name in STATUS_NAMES.items():
                    for o in f.get("options", []):
                        if o["name"] == name:
                            opts[key] = o["id"]
                self._board_fields[project_id] = {"field_id": f["id"], "options": opts}
                return self._board_fields[project_id]
        logger.warning("No Status field found on project %s", project_id)
        return None

    async def update_item_status(self, item_id: str, status_key: str, project_id: str) -> bool:
        board = await self.resolve_board_fields(project_id)
        if not board or status_key not in board["options"]:
            logger.warning("Cannot resolve status '%s' on project %s", status_key, project_id)
            return False
        option_id = board["options"][status_key]
        headers = {
            "Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "AgentManagerLocal/1.0"
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.github.com/graphql",
                    json={
                        "query": UPDATE_ITEM_STATUS_MUTATION,
                        "variables": {
                            "projectId": project_id,
                            "itemId": item_id,
                            "fieldId": board["field_id"],
                            "optionId": option_id
                        }
                    },
                    headers=headers
                )
                if resp.status_code != 200:
                    logger.error("GraphQL mutation failed with status %d: %s", resp.status_code, resp.text)
                    return False
                res_data = resp.json()
                if "errors" in res_data:
                    logger.error("GraphQL mutation returned errors: %s", res_data["errors"])
                    return False
                return bool(res_data.get("data", {}).get("updateProjectV2ItemFieldValue"))
        except Exception as e:
            logger.error("Failed to update item status: %s", e)
            return False
