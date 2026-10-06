"""
GitHub OAuth Client Service.
Manages OAuth redirect URLs, token exchange, and user profile retrieval.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import urllib.parse
from typing import Optional, Dict, Any
import httpx
from agent_manager.auth.config import (
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    get_allowed_github_users
)

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_API_URL = "https://api.github.com/user"


def get_github_oauth_url(redirect_uri: str, state: Optional[str] = None) -> str:
    """Constructs the GitHub OAuth authorization redirect URL."""
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "read:user user:email",
    }
    if state:
        params["state"] = state
    return f"{GITHUB_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


async def exchange_code_for_token(code: str, redirect_uri: str) -> Optional[str]:
    """Exchanges an OAuth temporary authorization code for a GitHub access token."""
    payload = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    headers = {"Accept": "application/json"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.post(GITHUB_TOKEN_URL, json=payload, headers=headers)
        if res.status_code == 200:
            data = res.json()
            return data.get("access_token")
    return None


async def get_github_user_profile(access_token: str) -> Optional[Dict[str, Any]]:
    """Fetches user profile information from the GitHub API using an access token."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Agent-Manager-Auth/1.0"
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.get(GITHUB_USER_API_URL, headers=headers)
        if res.status_code == 200:
            return res.json()
    return None


def is_user_authorized(username: Optional[str]) -> bool:
    """Verifies whether the authenticated GitHub user is allowed access."""
    if not username:
        return False
    allowed = get_allowed_github_users()
    return username.strip().lower() in allowed
