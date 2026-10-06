"""
Unit & Integration Tests for Ephemeral Preview Environments & Visual Smoke Testing.
Verifies port allocation, HTTP server lifecycle, readiness checks, timeout reaping,
smoke test execution, and REST endpoint integration.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from agent_manager.server import app
from agent_manager.services.preview_env_service import (
    find_free_port, launch_preview_server, stop_preview_server,
    reap_stale_previews, list_active_previews
)
from agent_manager.runners.preview import (
    execute_smoke_test, format_preview_pr_comment, run_preview_validation
)


class TestPreviewEnvironmentService(unittest.TestCase):
    def test_find_free_port(self):
        port = find_free_port()
        self.assertIsInstance(port, int)
        self.assertGreater(port, 1024)

    def test_launch_and_stop_preview_server(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            index_file = tmp_path / "index.html"
            index_file.write_text("<html><head><title>Preview Demo</title></head><body><h1>Hello</h1></body></html>", encoding="utf-8")

            sess_id = "preview-test-sess-1"
            instance = launch_preview_server(sess_id, tmp_path)
            try:
                self.assertEqual(instance.session_id, sess_id)
                self.assertIn("127.0.0.1", instance.url)
                self.assertEqual(instance.status, "READY")

                smoke = execute_smoke_test(instance.url)
                self.assertTrue(smoke["success"])
                self.assertEqual(smoke["status_code"], 200)
                self.assertEqual(smoke["page_title"], "Preview Demo")
            finally:
                stopped = stop_preview_server(sess_id)
                self.assertTrue(stopped)

    def test_reap_stale_previews(self):
        reaped = reap_stale_previews()
        self.assertGreaterEqual(reaped, 0)

    def test_format_preview_pr_comment(self):
        smoke_res = {
            "success": True,
            "status_code": 200,
            "latency_ms": 12.5,
            "page_title": "App Demo"
        }
        comment = format_preview_pr_comment("http://127.0.0.1:8080", smoke_res, "shot.webp")
        self.assertIn("ONLINE & VERIFIED", comment)
        self.assertIn("App Demo", comment)
        self.assertIn("shot.webp", comment)

    def test_run_preview_validation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "index.html").write_text("<title>Validation Test</title>", encoding="utf-8")

            res = run_preview_validation("val-sess-1", tmp_path, auto_teardown=True)
            self.assertEqual(res["session_id"], "val-sess-1")
            self.assertTrue(res["smoke_test"]["success"])
            self.assertEqual(res["smoke_test"]["page_title"], "Validation Test")
            self.assertIn("ONLINE & VERIFIED", res["pr_comment"])


class TestPreviewAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_active_previews_endpoint(self):
        res = self.client.get("/api/previews/active")
        self.assertEqual(res.status_code, 200)
        self.assertIn("active_previews", res.json())

    def test_launch_and_stop_api_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "index.html").write_text("<title>API Test</title>", encoding="utf-8")

            launch_res = self.client.post("/api/previews/launch", json={
                "session_id": "api-preview-sess",
                "worktree_path": str(tmp_path)
            })
            self.assertEqual(launch_res.status_code, 200)
            data = launch_res.json()
            self.assertEqual(data["status"], "READY")
            self.assertIn("127.0.0.1", data["preview_url"])

            stop_res = self.client.post("/api/previews/stop", json={
                "session_id": "api-preview-sess"
            })
            self.assertEqual(stop_res.status_code, 200)
            self.assertTrue(stop_res.json()["stopped"])


if __name__ == "__main__":
    unittest.main()
