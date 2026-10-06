"""
JWT Token Service for Agent Manager Authentication.
Signs, decodes, and verifies session tokens securely.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import time
from typing import Optional, Dict, Any
import jwt
from agent_manager.auth.config import AUTH_SECRET

ALGORITHM = "HS256"
DEFAULT_EXPIRY_DAYS = 7


def create_auth_token(
    username: str,
    avatar_url: Optional[str] = None,
    name: Optional[str] = None,
    expires_in_days: int = DEFAULT_EXPIRY_DAYS
) -> str:
    """Creates a signed JWT for the authenticated user session."""
    now = int(time.time())
    expires_at = now + (expires_in_days * 86400)
    payload = {
        "sub": username.lower(),
        "username": username,
        "avatar_url": avatar_url or "",
        "name": name or username,
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(payload, AUTH_SECRET, algorithm=ALGORITHM)


def verify_auth_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Verifies and decodes a JWT token. Returns payload dict or None if invalid."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, AUTH_SECRET, algorithms=[ALGORITHM])
        return payload
    except (jwt.PyJWTError, Exception):
        return None
