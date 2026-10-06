"""
Authentication & Access Control Module for Agent Manager.
Provides GitHub OAuth, JWT session verification, and route protection.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

from agent_manager.auth.config import (
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    AUTH_SECRET,
    ALLOWED_GITHUB_USERS,
    is_auth_enabled
)
from agent_manager.auth.jwt_service import create_auth_token, verify_auth_token
from agent_manager.auth.github_oauth import (
    get_github_oauth_url,
    exchange_code_for_token,
    get_github_user_profile,
    is_user_authorized
)
from agent_manager.auth.middleware import get_current_user, require_auth

__all__ = [
    "GITHUB_CLIENT_ID",
    "GITHUB_CLIENT_SECRET",
    "AUTH_SECRET",
    "ALLOWED_GITHUB_USERS",
    "is_auth_enabled",
    "create_auth_token",
    "verify_auth_token",
    "get_github_oauth_url",
    "exchange_code_for_token",
    "get_github_user_profile",
    "is_user_authorized",
    "get_current_user",
    "require_auth",
]
