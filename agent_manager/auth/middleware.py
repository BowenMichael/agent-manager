"""
Authentication Middleware and FastAPI Dependencies.
Extracts session identity from cookies or headers and guards sensitive endpoints.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from agent_manager.auth.config import COOKIE_NAME, is_auth_enabled
from agent_manager.auth.jwt_service import verify_auth_token
from agent_manager.auth.github_oauth import is_user_authorized


def extract_token_from_request(request: Request) -> Optional[str]:
    """Extracts auth token from Authorization header or HTTP-only session cookie."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return request.cookies.get(COOKIE_NAME)


def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """FastAPI dependency: Resolves current user or returns None if unauthenticated."""
    if not is_auth_enabled():
        return {"username": "local_dev", "sub": "local_dev", "authenticated": True}

    token = extract_token_from_request(request)
    payload = verify_auth_token(token)
    if not payload:
        return None

    username = payload.get("username")
    if not is_user_authorized(username):
        return None
    return payload


def require_auth(request: Request) -> Dict[str, Any]:
    """FastAPI dependency: Enforces that the request has an authorized session."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in with an authorized GitHub account."
        )
    return user
