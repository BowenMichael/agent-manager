"""
Unit & Integration Tests for Code Quality, Readability & Testability Metrics.
Adheres strictly to Anti-Monolith guidelines (< 250 lines).
"""

import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from agent_manager.server import app
from agent_manager.services.code_quality_service import (
    analyze_python_file,
    compute_readability_and_simplicity_metrics,
    compute_testability_metrics,
    generate_code_health_report,
)


class TestCodeQualityMetrics(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_analyze_python_file_ast(self):
        test_file = Path(__file__)
        analysis = analyze_python_file(test_file)
        self.assertIn("loc", analysis)
        self.assertGreater(analysis["loc"], 10)
        self.assertIn("functions", analysis)
        # Should have found this test method
        func_names = [f["name"] for f in analysis["functions"]]
        self.assertIn("test_analyze_python_file_ast", func_names)

    def test_readability_and_simplicity_metrics(self):
        metrics = compute_readability_and_simplicity_metrics()
        self.assertIn("simplicity_score", metrics)
        self.assertIn("root_file_count", metrics)
        self.assertIn("avg_lines_per_file", metrics)
        self.assertIn("avg_lines_per_function", metrics)
        self.assertIn("largest_files", metrics)
        self.assertIn("largest_functions", metrics)
        self.assertGreater(metrics["total_source_files"], 10)
        self.assertGreater(metrics["total_functions"], 10)

    def test_testability_metrics(self):
        test_metrics = compute_testability_metrics()
        self.assertIn("testability_score", test_metrics)
        self.assertIn("total_test_files", test_metrics)
        self.assertIn("total_test_cases", test_metrics)
        self.assertIn("unit_test_cases", test_metrics)
        self.assertIn("integration_test_cases", test_metrics)
        self.assertIn("test_to_code_ratio", test_metrics)
        self.assertGreater(test_metrics["total_test_files"], 10)
        self.assertGreater(test_metrics["total_test_cases"], 30)

    def test_code_health_api_endpoint(self):
        response = self.client.get("/api/telemetry/code-health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("composite_code_health_score", data)
        self.assertIn("readability_and_simplicity", data)
        self.assertIn("testability_and_coverage", data)
        self.assertIn("recommendations", data)


if __name__ == "__main__":
    unittest.main()
