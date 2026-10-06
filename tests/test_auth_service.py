"""
Unit tests for GitHub OAuth, JWT token service, and Auth Middleware.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import unittest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends, Request

from agent_manager.auth.jwt_service import create_auth_token, verify_auth_token
from agent_manager.auth.github_oauth import (
    get_github_oauth_url,
    is_user_authorized
)
from agent_manager.auth.config import is_auth_enabled
from agent_manager.auth.middleware import get_current_user, require_auth
from agent_manager.api.routes.auth import router as auth_router, get_callback_url


class TestAuthService(unittest.TestCase):
    """Test suite for authentication and token validation."""

    def test_jwt_create_and_verify_valid_token(self):
        """Verify token generation and decoding preserves user identity."""
        token = create_auth_token(username="BowenMichael", avatar_url="https://avatar.com/123.png")
        payload = verify_auth_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["username"], "BowenMichael")
        self.assertEqual(payload["sub"], "bowenmichael")
        self.assertEqual(payload["avatar_url"], "https://avatar.com/123.png")

    def test_jwt_verify_invalid_token(self):
        """Verify invalid or tampered tokens return None."""
        self.assertIsNone(verify_auth_token("invalid.token.string"))
        self.assertIsNone(verify_auth_token(None))
        self.assertIsNone(verify_auth_token(""))

    def test_is_user_authorized(self):
        """Verify user authorization checks against whitelist."""
        with patch("agent_manager.auth.github_oauth.get_allowed_github_users", return_value=["bowenmichael", "alice"]):
            self.assertTrue(is_user_authorized("BowenMichael"))
            self.assertTrue(is_user_authorized("bowenmichael"))
            self.assertTrue(is_user_authorized("alice"))
            self.assertFalse(is_user_authorized("malicious_user"))
            self.assertFalse(is_user_authorized(None))

    def test_get_github_oauth_url(self):
        """Verify OAuth URL contains client_id, scope, and redirect_uri."""
        with patch("agent_manager.auth.github_oauth.GITHUB_CLIENT_ID", "test-client-id"):
            url = get_github_oauth_url("https://agent-manager.com/callback", state="random-state")
            self.assertIn("client_id=test-client-id", url)
            self.assertIn("redirect_uri=https%3A%2F%2Fagent-manager.com%2Fcallback", url)
            self.assertIn("state=random-state", url)
            self.assertIn("scope=read%3Auser+user%3Aemail", url)


class TestAuthEndpoints(unittest.TestCase):
    """Test suite for /api/auth API routes."""

    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(auth_router)

        @self.app.get("/api/protected-route")
        def protected_endpoint(user: dict = Depends(require_auth)):
            return {"secret": "data", "user": user["username"]}

        self.client = TestClient(self.app)

    def test_auth_me_unauthenticated(self):
        """Verify /api/auth/me returns authenticated=False when auth enabled."""
        with patch("agent_manager.auth.middleware.is_auth_enabled", return_value=True), \
             patch("agent_manager.api.routes.auth.is_auth_enabled", return_value=True):
            res = self.client.get("/api/auth/me")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertFalse(data["authenticated"])
            self.assertTrue(data["auth_enabled"])

    def test_auth_me_authenticated_via_cookie(self):
        """Verify /api/auth/me returns authenticated user details from valid cookie."""
        token = create_auth_token(username="BowenMichael", avatar_url="https://avatar.com/me.png")
        with patch("agent_manager.auth.middleware.is_auth_enabled", return_value=True), \
             patch("agent_manager.api.routes.auth.is_auth_enabled", return_value=True), \
             patch("agent_manager.auth.middleware.is_user_authorized", return_value=True):
            self.client.cookies.set("agent_manager_session", token)
            res = self.client.get("/api/auth/me")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertTrue(data["authenticated"])
            self.assertEqual(data["username"], "BowenMichael")

    def test_logout_endpoint(self):
        """Verify /api/auth/logout deletes the session cookie."""
        res = self.client.post("/api/auth/logout")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("logged_out"))

    def test_protected_route_blocks_unauthenticated_request(self):
        """Verify require_auth raises 401 when unauthenticated and auth is enabled."""
        with patch("agent_manager.auth.middleware.is_auth_enabled", return_value=True):
            res = self.client.get("/api/protected-route")
            self.assertEqual(res.status_code, 401)

    def test_protected_route_allows_authenticated_request(self):
        """Verify require_auth grants access when valid session token is provided."""
        token = create_auth_token(username="BowenMichael")
        with patch("agent_manager.auth.middleware.is_auth_enabled", return_value=True), \
             patch("agent_manager.auth.middleware.is_user_authorized", return_value=True):
            self.client.cookies.set("agent_manager_session", token)
            res = self.client.get("/api/protected-route")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["user"], "BowenMichael")

    @patch("agent_manager.api.routes.auth.exchange_code_for_token", new_callable=AsyncMock)
    @patch("agent_manager.api.routes.auth.get_github_user_profile", new_callable=AsyncMock)
    def test_github_callback_success(self, mock_profile, mock_exchange):
        """Verify successful OAuth code exchange sets cookie and redirects to root."""
        mock_exchange.return_value = "gho_mock_access_token"
        mock_profile.return_value = {"login": "BowenMichael", "name": "Michael", "avatar_url": "https://avatar.png"}
        with patch("agent_manager.api.routes.auth.is_user_authorized", return_value=True):
            res = self.client.get("/api/auth/github/callback?code=valid_test_code", follow_redirects=False)
            self.assertEqual(res.status_code, 302)
            self.assertEqual(res.headers["location"], "/")
            self.assertIn("agent_manager_session", res.headers.get("set-cookie", ""))


if __name__ == "__main__":
    unittest.main()
