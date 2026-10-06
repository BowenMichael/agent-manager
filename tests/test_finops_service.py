"""
Unit Tests for FinOps & Dynamic Token Arbitrage Service.
Tests budget configs, spend evaluation, arbitrage downgrades, and API endpoints.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from agent_manager.services.finops_service import (
    load_budget_configurations, save_budget_configurations,
    get_repo_budget, set_repo_budget,
    evaluate_repo_spend, apply_token_arbitrage
)
from agent_manager.server import app


class TestFinOpsService(unittest.TestCase):
    """Test suite for FinOps per-repo budgets and token arbitrage."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.patcher = patch(
            "agent_manager.services.finops_service.get_budgets_file_path",
            return_value=Path(self.tmpdir.name) / "test_budgets.json"
        )
        self.patcher.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.patcher.stop()
        self.tmpdir.cleanup()

    def test_budget_config_defaults_and_override(self):
        default_cfg = get_repo_budget("BowenMichael/fit-elo")
        self.assertEqual(default_cfg["daily_limit_usd"], 15.0)

        updated = set_repo_budget("BowenMichael/fit-elo", daily_limit=25.0, monthly_limit=250.0)
        self.assertEqual(updated["daily_limit_usd"], 25.0)
        self.assertEqual(updated["monthly_limit_usd"], 250.0)

        loaded = load_budget_configurations()
        self.assertIn("BowenMichael/fit-elo", loaded)

    def test_evaluate_spend_normal(self):
        set_repo_budget("test/repo", daily_limit=10.0, monthly_limit=100.0)
        s1 = MagicMock()
        s1.repo = "test/repo"
        s1.input_tokens = 50_000
        s1.output_tokens = 5_000
        s1.thinking_tokens = 0
        s1.cache_read_tokens = 0
        s1.model = "gemini-2.5-pro"
        s1.created_at = "2026-10-06T00:00:00Z"

        res = evaluate_repo_spend("test/repo", [s1])
        self.assertEqual(res["status"], "NORMAL")
        self.assertTrue(res["allow_dispatch"])
        self.assertFalse(res["arbitrage_active"])

    def test_evaluate_spend_arbitrage_and_exceeded(self):
        set_repo_budget("test/repo", daily_limit=1.0, monthly_limit=10.0)
        # 1M output tokens on pro is > $1.00
        s_heavy = MagicMock()
        s_heavy.repo = "test/repo"
        s_heavy.input_tokens = 500_000
        s_heavy.output_tokens = 200_000
        s_heavy.thinking_tokens = 0
        s_heavy.cache_read_tokens = 0
        s_heavy.model = "gemini-2.5-pro"
        s_heavy.created_at = "2026-10-06T00:00:00Z"

        res = evaluate_repo_spend("test/repo", [s_heavy])
        self.assertEqual(res["status"], "EXCEEDED")
        self.assertFalse(res["allow_dispatch"])

    def test_apply_token_arbitrage_downgrade(self):
        set_repo_budget("test/repo", daily_limit=1.0, monthly_limit=10.0)
        s_heavy = MagicMock()
        s_heavy.repo = "test/repo"
        s_heavy.input_tokens = 500_000
        s_heavy.output_tokens = 200_000
        s_heavy.thinking_tokens = 0
        s_heavy.cache_read_tokens = 0
        s_heavy.model = "gemini-2.5-pro"
        s_heavy.created_at = "2026-10-06T00:00:00Z"

        model, effort, downgraded = apply_token_arbitrage("gemini-2.5-pro", "high", "test/repo", [s_heavy])
        self.assertTrue(downgraded)
        self.assertEqual(model, "gemini-2.5-flash")
        self.assertEqual(effort, "low")

    def test_api_finops_budgets(self):
        res = self.client.get("/api/finops/budgets")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("budgets", data)

        post_res = self.client.post("/api/finops/budgets", json={
            "repo": "BowenMichael/full_swing_scraper",
            "daily_limit_usd": 20.0,
            "monthly_limit_usd": 200.0,
        })
        self.assertEqual(post_res.status_code, 200)
        self.assertEqual(post_res.json()["status"], "updated")


if __name__ == "__main__":
    unittest.main()
