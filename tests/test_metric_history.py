"""
Unit Tests for Metric History & Traceability Service.
Validates snapshot recording, persistence, trend delta computation, and API endpoints.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from agent_manager.services.metric_history_service import (
    record_metric_snapshot, load_metric_history, save_metric_history,
    compute_metric_trends
)
from agent_manager.services.manifesto_metrics import generate_manifesto_compliance_report
from agent_manager.server import app


class TestMetricHistoryService(unittest.TestCase):
    """Tests for time-series snapshot storage and trajectory computation."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.patcher = patch(
            "agent_manager.services.metric_history_service.get_history_file_path",
            return_value=Path(self.tmpdir.name) / "test_history.json"
        )
        self.patcher.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.patcher.stop()
        self.tmpdir.cleanup()

    def test_record_and_load_snapshots(self):
        sample_report_1 = {
            "manifesto_health_index": 20.0,
            "grade": "GROUND_FLOOR",
            "pillars": {"I_observability": {"score": 20.0}}
        }
        snap1 = record_metric_snapshot(sample_report_1, git_commit="abc111")
        self.assertEqual(snap1["manifesto_health_index"], 20.0)

        sample_report_2 = {
            "manifesto_health_index": 45.0,
            "grade": "EARLY_FOUNDATION",
            "pillars": {"I_observability": {"score": 60.0}}
        }
        snap2 = record_metric_snapshot(sample_report_2, git_commit="abc222")
        self.assertEqual(snap2["manifesto_health_index"], 45.0)

        history = load_metric_history()
        self.assertEqual(len(history), 2)

    def test_compute_metric_trends(self):
        records = [
            {"id": "s1", "timestamp": "2026-10-01T00:00:00Z", "git_commit": "c1", "manifesto_health_index": 25.0, "pillars": {"I": 20.0}},
            {"id": "s2", "timestamp": "2026-10-05T00:00:00Z", "git_commit": "c2", "manifesto_health_index": 55.0, "pillars": {"I": 80.0}},
        ]
        save_metric_history(records)

        trends = compute_metric_trends()
        self.assertEqual(trends["status"], "TRACKED")
        self.assertEqual(trends["baseline_score"], 25.0)
        self.assertEqual(trends["current_score"], 55.0)
        self.assertEqual(trends["overall_delta"], 30.0)
        self.assertEqual(trends["direction"], "improving")
        self.assertEqual(trends["pillar_deltas"]["I"], 60.0)

    def test_api_manifesto_history(self):
        res = self.client.get("/api/telemetry/manifesto-history")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)
        self.assertIn("direction", data)

    def test_auto_snapshot_on_report_generation(self):
        report = generate_manifesto_compliance_report()
        self.assertIn("manifesto_health_index", report)
        history = load_metric_history()
        self.assertGreaterEqual(len(history), 1)


if __name__ == "__main__":
    unittest.main()
