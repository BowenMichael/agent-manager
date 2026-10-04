import os
import json
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
import httpx

from agent_manager.config import (
    GITHUB_PERSONAL_ACCESS_TOKEN, PROJECT_BOARD_IDS, PROJECT_BOARD_ID
)
from agent_manager.utils.workspace import find_local_workspace
from agent_manager.runner import AgentRunnerManager

logger = logging.getLogger("agent_manager.services.projects")

PROJECTS_CONFIG: List[Dict[str, Any]] = [
    {
        "id": "fit-elo",
        "name": "FitElo",
        "repo": "BowenMichael/fit-elo",
        "stack": "Expo / React Native, TypeScript, Jest",
        "icon": "🏋️",
        "description": "Adaptive workout tracker & Elo fitness progression platform",
    },
    {
        "id": "better-business-deal",
        "name": "Better Business Deal",
        "repo": "BowenMichael/better_buisness_deal",
        "stack": "Expo / React Native, TypeScript, Jest",
        "icon": "💼",
        "description": "Commercial deal analysis, underwriting & business evaluation suite",
    },
    {
        "id": "leanfolio",
        "name": "Leanfolio",
        "repo": "BowenMichael/leanfolio",
        "stack": "Next.js 12, React 17, Material-UI, ESLint",
        "icon": "📈",
        "description": "Minimalist, high-performance developer portfolio & engineering showcase",
    },
    {
        "id": "agent-manager",
        "name": "Agent Manager",
        "repo": "BowenMichael/agent-manager",
        "stack": "FastAPI, Python 3.12, Antigravity SDK, WebSockets",
        "icon": "🤖",
        "description": "Autonomous agent orchestration control plane & GitHub issue dispatcher",
    },
    {
        "id": "f1-frontend",
        "name": "F1 Frontend",
        "repo": "BowenMichael/f1-frontend",
        "stack": "Next.js 14, TypeScript, Tailwind, Canvas",
        "icon": "🏎️",
        "description": "Formula 1 telemetry analysis, track replay & leaderboard dashboard",
    },
]

BOARD_ITEMS_QUERY = """
query($projectId: ID!) {
  node(id: $projectId) {
    ... on ProjectV2 {
      title
      number
      url
      items(first: 100) {
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
              state
              url
              repository { nameWithOwner }
            }
            ... on PullRequest {
              number
              title
              state
              url
              repository { nameWithOwner }
            }
          }
        }
      }
    }
  }
}
"""


async def fetch_board_items() -> List[Dict[str, Any]]:
    """Fetches all items across configured GitHub Project Boards via GraphQL."""
    if not GITHUB_PERSONAL_ACCESS_TOKEN:
        return []

    headers = {
        "Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "AgentManagerLocal/1.0"
    }

    items_list = []
    seen_keys = set()

    async with httpx.AsyncClient(timeout=15.0) as client:
        for bid in PROJECT_BOARD_IDS:
            try:
                resp = await client.post(
                    "https://api.github.com/graphql",
                    json={"query": BOARD_ITEMS_QUERY, "variables": {"projectId": bid}},
                    headers=headers
                )
                if resp.status_code != 200:
                    continue
                node = resp.json().get("data", {}).get("node", {}) or {}
                nodes = node.get("items", {}).get("nodes", [])

                for item in nodes:
                    content = item.get("content") or {}
                    repo_info = content.get("repository") or {}
                    repo_name = repo_info.get("nameWithOwner", "")
                    num = content.get("number")
                    if not repo_name or not num:
                        continue

                    key = f"{repo_name}#{num}"
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    status = "📥 Backlog"
                    for fv in item.get("fieldValues", {}).get("nodes", []):
                        if fv.get("field", {}).get("name") == "Status":
                            status = fv.get("name", "📥 Backlog")
                            break

                    items_list.append({
                        "id": item.get("id"),
                        "repo": repo_name,
                        "number": num,
                        "title": content.get("title", ""),
                        "body": content.get("body", "") or "",
                        "state": content.get("state", "OPEN"),
                        "url": content.get("url", f"https://github.com/{repo_name}/issues/{num}"),
                        "status": status,
                        "board_title": node.get("title", ""),
                        "board_url": node.get("url", "")
                    })
            except Exception as e:
                logger.error(f"Error fetching items from board {bid}: {e}")

    return items_list
