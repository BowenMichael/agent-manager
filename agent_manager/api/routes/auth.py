"""
Authentication API Endpoints.
Handles GitHub OAuth login, callback token exchange, session queries, and logout.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import os
from typing import Optional
from fastapi import APIRouter, Request, Response, status, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel

from agent_manager.auth.config import (
    COOKIE_NAME,
    is_auth_enabled,
    GITHUB_CLIENT_ID
)
from agent_manager.auth.jwt_service import create_auth_token
from agent_manager.auth.github_oauth import (
    get_github_oauth_url,
    exchange_code_for_token,
    get_github_user_profile,
    is_user_authorized
)
from agent_manager.auth.middleware import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthStatusResponse(BaseModel):
    authenticated: bool
    auth_enabled: bool
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    name: Optional[str] = None


def get_callback_url(request: Request) -> str:
    """Resolves canonical OAuth callback URL respecting reverse proxy HTTPS headers and env vars."""
    app_url = os.getenv("APP_URL") or os.getenv("RENDER_EXTERNAL_URL")
    if app_url:
        return f"{app_url.rstrip('/')}/api/auth/github/callback"
    url = str(request.url_for("github_callback"))
    proto = request.headers.get("x-forwarded-proto", "")
    if proto == "https" and url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    return url


@router.get("/me", response_model=AuthStatusResponse)
def get_auth_status(request: Request):
    """Returns the current user's session status and profile."""
    enabled = is_auth_enabled()
    user = get_current_user(request)
    if not user or not user.get("username"):
        return AuthStatusResponse(authenticated=not enabled, auth_enabled=enabled)

    return AuthStatusResponse(
        authenticated=True,
        auth_enabled=enabled,
        username=user.get("username"),
        avatar_url=user.get("avatar_url", ""),
        name=user.get("name", user.get("username"))
    )


@router.get("/github/login")
def github_login(request: Request):
    """Initiates GitHub OAuth flow by redirecting to GitHub authorization page."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub OAuth is not configured. Please set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET."
        )
    redirect_uri = get_callback_url(request)
    oauth_url = get_github_oauth_url(redirect_uri)
    return RedirectResponse(url=oauth_url)


def _create_auth_cookie_redirect(token: str, request: Request) -> RedirectResponse:
    """Sets HTTP-only authentication cookie and creates redirect response."""
    is_https = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https"
        or bool(os.getenv("RENDER_EXTERNAL_URL"))
    )
    redirect = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    redirect.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=is_https,
        samesite="lax",
        max_age=7 * 86400
    )
    return redirect


@router.get("/github/callback")
async def github_callback(code: str, request: Request, response: Response):
    """Exchanges code for access token, fetches profile, and sets auth cookie."""
    redirect_uri = get_callback_url(request)
    access_token = await exchange_code_for_token(code, redirect_uri)
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to retrieve access token from GitHub."
        )

    profile = await get_github_user_profile(access_token)
    if not profile or not profile.get("login"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to retrieve GitHub profile."
        )

    username = profile["login"]
    if not is_user_authorized(username):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User '{username}' is not authorized to access Agent Manager."
        )

    token = create_auth_token(
        username=username,
        avatar_url=profile.get("avatar_url", ""),
        name=profile.get("name", username)
    )
    return _create_auth_cookie_redirect(token, request)


@router.post("/logout")
def logout(response: Response):
    """Clears the session cookie."""
    res = JSONResponse(content={"logged_out": True})
    res.delete_cookie(key=COOKIE_NAME)
    return res
