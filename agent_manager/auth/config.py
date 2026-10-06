"""
Authentication Configuration Module.
Resolves GitHub OAuth credentials, session secrets, and allowed users.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import os
from typing import List

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "").strip()
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "").strip()
AUTH_SECRET = os.getenv("AUTH_SECRET", "agent-manager-default-secret-key-32b").strip()
COOKIE_NAME = "agent_manager_session"


def get_allowed_github_users() -> List[str]:
    """Returns list of lowercase GitHub usernames permitted to access the dashboard."""
    raw = os.getenv("ALLOWED_GITHUB_USERS", "BowenMichael").strip()
    if not raw:
        return ["bowenmichael"]
    return [u.strip().lower() for u in raw.split(",") if u.strip()]


ALLOWED_GITHUB_USERS = get_allowed_github_users()


def is_auth_enabled() -> bool:
    """Determines whether authentication gating is active."""
    explicit_flag = os.getenv("AUTH_ENABLED", "").strip().lower()
    if explicit_flag in ("1", "true", "yes"):
        return True
    if explicit_flag in ("0", "false", "no"):
        return False
    # If GitHub Client ID and Secret are configured, enable by default
    return bool(GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET)
