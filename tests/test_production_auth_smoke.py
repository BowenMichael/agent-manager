"""
Production Deployment Authentication Smoke & Verification Tests.
Verifies live endpoints on Render (https://agent-manager-api.onrender.com).
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import os
import unittest
import urllib.request
import urllib.error
import json

PROD_URL = os.getenv("PROD_URL", "https://agent-manager-api.onrender.com").rstrip("/")


class TestProductionAuthSmoke(unittest.TestCase):
    """Verifies authentication readiness and live system endpoints on Render."""

    def test_live_healthz_endpoint(self):
        """Verifies /healthz probe is responsive and returns healthy database state."""
        req = urllib.request.Request(f"{PROD_URL}/healthz", headers={"User-Agent": "SmokeTest/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                self.assertEqual(response.status, 200)
                data = json.loads(response.read().decode("utf-8"))
                self.assertEqual(data.get("status"), "healthy")
                self.assertEqual(data.get("service"), "agent-manager")
        except urllib.error.URLError as e:
            self.skipTest(f"Live Render environment unavailable: {e}")

    def test_live_auth_status_endpoint(self):
        """Verifies /api/auth/me returns valid JSON with auth_enabled and authenticated fields."""
        req = urllib.request.Request(f"{PROD_URL}/api/auth/me", headers={"User-Agent": "SmokeTest/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                self.assertEqual(response.status, 200)
                data = json.loads(response.read().decode("utf-8"))
                self.assertIn("authenticated", data)
                self.assertIn("auth_enabled", data)
        except urllib.error.URLError as e:
            self.skipTest(f"Live Render environment unavailable: {e}")

    def test_live_github_login_redirect_or_config(self):
        """Verifies /api/auth/github/login initiates OAuth redirect or returns clean 503 if pending config."""
        req = urllib.request.Request(f"{PROD_URL}/api/auth/github/login", headers={"User-Agent": "SmokeTest/1.0"})
        try:
            # Opener that does not follow redirects so we can inspect the 307/302
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def http_error_302(self, req, fp, code, msg, headers):
                    return fp
                http_error_301 = http_error_302
                http_error_303 = http_error_302
                http_error_307 = http_error_302

            opener = urllib.request.build_opener(NoRedirect)
            resp = opener.open(req, timeout=10)
            self.assertIn(resp.status, (200, 302, 307, 503))
        except urllib.error.HTTPError as e:
            self.assertIn(e.code, (302, 307, 503))
        except urllib.error.URLError as e:
            self.skipTest(f"Live Render environment unavailable: {e}")


if __name__ == "__main__":
    unittest.main()
