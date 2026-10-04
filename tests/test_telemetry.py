import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient

from agent_manager.telemetry import (
    record_token_usage,
    get_timescale_metrics,
    sync_from_sessions_cache
)
from agent_manager.server import app

class TestTokenTelemetry(unittest.TestCase):
    def setUp(self):
        self.mock_records = []
        self.patcher_load = patch("agent_manager.telemetry.load_telemetry_records", side_effect=lambda: self.mock_records)
        self.patcher_save = patch("agent_manager.telemetry.save_telemetry_records", side_effect=lambda r: setattr(self, "mock_records", r))
        self.patcher_load.start()
        self.patcher_save.start()

    def tearDown(self):
        self.patcher_load.stop()
        self.patcher_save.stop()

    def test_record_token_usage_basic(self):
        record = record_token_usage(
            session_id="sess-1",
            repo="BowenMichael/f1-frontend",
            model="gemini-3.8-flash",
            input_tokens=1000,
            output_tokens=200,
            thinking_tokens=50,
            cache_read_tokens=5000,
            total_tokens=1250
        )
        self.assertEqual(record["session_id"], "sess-1")
        self.assertEqual(record["total_tokens"], 1250)
        self.assertEqual(len(self.mock_records), 1)

    def test_record_token_usage_update_monotonic(self):
        record_token_usage("sess-1", "repo", "flash", 100, 50, 0, 0, 150)
        # Update with higher values
        record_token_usage("sess-1", "repo", "flash", 200, 80, 0, 0, 280)
        self.assertEqual(len(self.mock_records), 1)
        self.assertEqual(self.mock_records[0]["total_tokens"], 280)
        self.assertEqual(self.mock_records[0]["input_tokens"], 200)

    def test_timescale_metrics_aggregation(self):
        now = datetime.now(timezone.utc)
        # Record 1: 30 minutes ago (in 1h, 24h, 7d, 30d, all-time)
        t_30m = (now - timedelta(minutes=30)).isoformat()
        record_token_usage("s1", "repo-a", "flash", 100, 50, 0, 1000, 150, timestamp=t_30m)

        # Record 2: 3 hours ago (in 24h, 7d, 30d, all-time; not in 1h)
        t_3h = (now - timedelta(hours=3)).isoformat()
        record_token_usage("s2", "repo-a", "pro", 300, 100, 0, 2000, 400, timestamp=t_3h)

        # Record 3: 3 days ago (in 7d, 30d, all-time; not in 24h)
        t_3d = (now - timedelta(days=3)).isoformat()
        record_token_usage("s3", "repo-b", "flash", 500, 200, 0, 3000, 700, timestamp=t_3d)

        # Record 4: 15 days ago (in 30d, all-time; not in 7d)
        t_15d = (now - timedelta(days=15)).isoformat()
        record_token_usage("s4", "repo-b", "sonnet", 1000, 400, 0, 4000, 1400, timestamp=t_15d)

        metrics = get_timescale_metrics(reference_time=now)
        summary = metrics["summary"]

        self.assertEqual(summary["last_1h_tokens"], 150)
        self.assertEqual(summary["last_24h_tokens"], 550) # 150 + 400
        self.assertEqual(summary["last_7d_tokens"], 1250) # 550 + 700
        self.assertEqual(summary["last_30d_tokens"], 2650) # 1250 + 1400
        self.assertEqual(summary["all_time_tokens"], 2650)
        self.assertEqual(summary["all_time_cache_read_tokens"], 10000)
        self.assertEqual(summary["total_sessions_tracked"], 4)

        # Verify model breakdown
        models = {m["model"]: m["tokens"] for m in metrics["model_breakdown"]}
        self.assertEqual(models["flash"], 850)
        self.assertEqual(models["pro"], 400)
        self.assertEqual(models["sonnet"], 1400)

        # Verify hourly and daily trends exist
        self.assertEqual(len(metrics["hourly_trend"]), 24)
        self.assertEqual(len(metrics["daily_trend"]), 30)

    def test_sync_from_sessions_cache(self):
        class DummySession:
            def __init__(self, sid, repo, model, inp, out, thk, cred, tot, ts):
                self.id = sid
                self.repo = repo
                self.model = model
                self.input_tokens = inp
                self.output_tokens = out
                self.thinking_tokens = thk
                self.cache_read_tokens = cred
                self.total_tokens = tot
                self.last_activity_at = ts
                self.created_at = ts

        sessions = [
            DummySession("sess-a", "repo-1", "flash", 100, 20, 0, 500, 120, "2026-10-01T12:00:00Z"),
            DummySession("sess-b", "repo-2", "pro", 200, 50, 0, 1000, 250, "2026-10-02T12:00:00Z")
        ]

        count = sync_from_sessions_cache(sessions)
        self.assertEqual(count, 2)
        self.assertEqual(len(self.mock_records), 2)

    def test_api_telemetry_tokens_endpoint(self):
        client = TestClient(app)
        response = client.get("/api/telemetry/tokens")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("summary", data)
        self.assertIn("hourly_trend", data)
        self.assertIn("daily_trend", data)
        self.assertIn("model_breakdown", data)
        self.assertIn("repo_breakdown", data)

if __name__ == "__main__":
    unittest.main()
