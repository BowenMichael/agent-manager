import logging
import httpx
from typing import Optional
from agent_manager.config import GITHUB_PERSONAL_ACCESS_TOKEN

logger = logging.getLogger("agent_manager.github")

async def post_issue_comment(repo: str, issue_number: int, body: str) -> Optional[dict]:
    """
    Posts a comment on a GitHub issue using GitHub REST API.
    Uses GITHUB_PERSONAL_ACCESS_TOKEN.
    """
    if not GITHUB_PERSONAL_ACCESS_TOKEN:
        logger.warning("GITHUB_PERSONAL_ACCESS_TOKEN not set; skipping GitHub comment.")
        return None

    if not repo or not issue_number:
        logger.warning(f"Invalid repo ({repo}) or issue_number ({issue_number}) for GitHub comment.")
        return None

    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    headers = {
        "Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AgentManagerLocal/1.0"
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json={"body": body}, headers=headers)
            if resp.status_code in [200, 201]:
                logger.info(f"Successfully posted comment on GitHub Issue {repo}#{issue_number}")
                return resp.json()
            else:
                logger.error(
                    f"Failed to post comment to {repo}#{issue_number}: HTTP {resp.status_code} - {resp.text}"
                )
                return None
    except Exception as e:
        logger.exception(f"Exception posting comment to {repo}#{issue_number}: {e}")
        return None
