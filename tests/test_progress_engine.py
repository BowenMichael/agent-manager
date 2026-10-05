"""
Unit & Integration Tests for Metric-Driven Autonomous Progress Engine.
Adheres strictly to Anti-Monolith guidelines (< 250 lines).
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from agent_manager.server import app
from agent_manager.cron.progress_engine import MetricDrivenProgressEngine, progress_engine


class TestProgressEngine(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("agent_manager.cron.progress_engine.generate_code_health_report")
    def test_evaluate_next_target_finds_monolith(self, mock_health):
        mock_health.return_value = {
            "readability_and_simplicity": {"max_lines_in_file": 350, "bloated_functions_count": 0},
            "root_hygiene": {"root_loose_files_count": 0},
            "testability_and_coverage": {"test_to_code_ratio": 1.0}
        }
        engine = MetricDrivenProgressEngine()
        target = engine.evaluate_next_target()
        self.assertIsNotNone(target)
        self.assertEqual(target["issue_number"], 100)
        self.assertEqual(target["metric_id"], "anti_monolith_refactor")

    @patch("agent_manager.cron.progress_engine.inspect_active_local_agents")
    def test_check_and_advance_busy_agent(self, mock_inspect):
        # When an active agent is working, do nothing extra
        mock_inspect.return_value = (["agent-sess-1"], {"bowenmichael/agent-manager#100"}, [])
        
        engine = MetricDrivenProgressEngine()
        import asyncio
        res = asyncio.run(engine.check_and_advance(dry_run=True))
        
        self.assertEqual(res["status"], "BUSY")
        self.assertEqual(res["action"], "MONITOR")
        self.assertIn("agent-sess-1", res["active_agents"])

    @patch("agent_manager.cron.progress_engine.generate_code_health_report")
    @patch("agent_manager.cron.progress_engine.inspect_active_local_agents")
    def test_check_and_advance_idle_identifies_task(self, mock_inspect, mock_health):
        mock_health.return_value = {
            "readability_and_simplicity": {"max_lines_in_file": 350, "bloated_functions_count": 0},
            "root_hygiene": {"root_loose_files_count": 0},
            "testability_and_coverage": {"test_to_code_ratio": 1.0}
        }
        # When idle, identifies next metric task
        mock_inspect.return_value = ([], set(), [])
        
        engine = MetricDrivenProgressEngine()
        import asyncio
        res = asyncio.run(engine.check_and_advance(dry_run=True))
        
        self.assertEqual(res["status"], "NEXT_TARGET_IDENTIFIED")
        self.assertEqual(res["target_issue"], 100)
        self.assertTrue(res["dry_run"])

    def test_progress_engine_api_endpoints(self):
        # Test status endpoint
        res_status = self.client.get("/api/cron/progress-status")
        self.assertEqual(res_status.status_code, 200)
        data_status = res_status.json()
        self.assertIn("next_metric_target", data_status)
        self.assertIn(data_status["next_metric_target"]["issue_number"], [100, 101, 39, 18, 90])

        # Test advance dry-run endpoint
        res_advance = self.client.post("/api/cron/progress-now?dry_run=true")
        self.assertEqual(res_advance.status_code, 200)
        data_advance = res_advance.json()
        self.assertIn("status", data_advance)


if __name__ == "__main__":
    unittest.main()
