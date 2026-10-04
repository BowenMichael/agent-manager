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

async def merge_pull_request(repo: str, pr_number: int) -> Optional[dict]:
    """
    Merges a pull request using GitHub REST API.
    Uses GITHUB_PERSONAL_ACCESS_TOKEN.
    """
    if not GITHUB_PERSONAL_ACCESS_TOKEN:
        logger.warning("GITHUB_PERSONAL_ACCESS_TOKEN not set; skipping GitHub PR merge.")
        return None

    if not repo or not pr_number:
        logger.warning(f"Invalid repo ({repo}) or pr_number ({pr_number}) for GitHub PR merge.")
        return None

    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/merge"
    headers = {
        "Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AgentManagerLocal/1.0"
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.put(url, json={"merge_method": "squash"}, headers=headers)
            if resp.status_code in [200, 201]:
                logger.info(f"Successfully merged PR on GitHub: {repo}#{pr_number}")
                return resp.json()
            else:
                logger.error(
                    f"Failed to merge PR {repo}#{pr_number}: HTTP {resp.status_code} - {resp.text}"
                )
                return None
    except Exception as e:
        logger.exception(f"Exception merging PR {repo}#{pr_number}: {e}")
        return None

async def find_pr_for_branch(repo: str, branch: str) -> Optional[int]:
    """Finds an open pull request for the given branch."""
    if not GITHUB_PERSONAL_ACCESS_TOKEN:
        return None

    owner = repo.split('/')[0] if '/' in repo else repo
    url = f"https://api.github.com/repos/{repo}/pulls?state=open&head={owner}:{branch}"
    headers = {
        "Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AgentManagerLocal/1.0"
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0:
                    return data[0]["number"]
            return None
    except Exception as e:
        logger.exception(f"Exception finding PR for {repo}:{branch}: {e}")
        return None
