import unittest
from unittest.mock import patch
from pathlib import Path
import json
from fastapi.testclient import TestClient

from agent_manager.server import app
from agent_manager.storage import save_settings, load_settings, _atomic_write_json


class TestSettingsErrorHandling(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_settings_get_and_post_success(self):
        """Verifies GET and POST /api/settings function properly and return valid JSON."""
        get_res = self.client.get("/api/settings")
        self.assertEqual(get_res.status_code, 200)
        self.assertIn("application/json", get_res.headers.get("content-type", ""))
        data = get_res.json()
        self.assertIn("default_model", data)

        post_res = self.client.post("/api/settings", json={
            "default_model": "gemini-3.8-flash",
            "default_effort": "high"
        })
        self.assertEqual(post_res.status_code, 200)
        self.assertIn("application/json", post_res.headers.get("content-type", ""))
        post_data = post_res.json()
        self.assertEqual(post_data.get("default_model"), "gemini-3.8-flash")
        self.assertEqual(post_data.get("default_effort"), "high")

    def test_settings_persistence_failure_returns_structured_json_500(self):
        """
        Verifies that when settings persistence encounters an error, the endpoint
        returns a structured JSON error response (with 'detail') instead of raw text/HTML.
        """
        with patch("agent_manager.api.settings.save_settings", side_effect=IOError("Disk write failed: permission denied")):
            res = self.client.post("/api/settings", json={"default_model": "gemini-3.8-flash"})
            self.assertEqual(res.status_code, 500)
            self.assertIn("application/json", res.headers.get("content-type", ""))
            
            # Must be valid parseable JSON with detail key
            err_json = res.json()
            self.assertIn("detail", err_json)
            self.assertIn("Disk write failed", err_json["detail"])

    def test_global_exception_handler_returns_json_on_unhandled_error(self):
        """
        Verifies that any unexpected unhandled exception triggers the global exception handler,
        returning structured JSON with status 500 and Content-Type application/json.
        """
        with patch("agent_manager.api.settings.config.get_cli_overage_credits", side_effect=RuntimeError("Unexpected crash")):
            res = self.client.get("/api/settings")
            self.assertEqual(res.status_code, 500)
            self.assertIn("application/json", res.headers.get("content-type", ""))
            err_json = res.json()
            self.assertIn("detail", err_json)
            self.assertIn("Failed to fetch settings", err_json["detail"])

    def test_atomic_write_json_resilience(self, tmp_path=None):
        """Verifies _atomic_write_json safely writes and handles file creation."""
        test_file = Path("data") / "test_atomic.json"
        try:
            payload = {"test_key": "test_value_123"}
            _atomic_write_json(test_file, payload)
            self.assertTrue(test_file.exists())
            with open(test_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(saved, payload)
        finally:
            if test_file.exists():
                test_file.unlink(missing_ok=True)

    def test_global_exception_handler_direct(self):
        """Verifies that an unhandled exception in an endpoint returns JSON via global handler."""
        @app.get("/api/test-crash-unhandled")
        async def crash_endpoint():
            raise ZeroDivisionError("Crash simulated")

        res = self.client.get("/api/test-crash-unhandled")
        self.assertEqual(res.status_code, 500)
        self.assertIn("application/json", res.headers.get("content-type", ""))
        err_json = res.json()
        self.assertIn("detail", err_json)
        self.assertIn("Internal Server Error: Crash simulated", err_json["detail"])


if __name__ == "__main__":
    unittest.main()
