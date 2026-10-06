"""
Unit Tests for Cross-Repository Task Orchestrator.
Tests contract drift detection, multi-repo plans, PR linking, and API endpoints.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from agent_manager.services.cross_repo_orchestrator import (
    load_orchestration_plans, save_orchestration_plans,
    detect_contract_files, resolve_dependent_repos,
    create_orchestration_plan, format_cross_reference_comment,
    update_plan_pr_link
)
from agent_manager.services.manifesto_metrics import evaluate_swarm_concurrency
from agent_manager.server import app


class TestCrossRepoOrchestrator(unittest.TestCase):
    """Test suite for cross-repository orchestration and contract sync."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.patcher = patch(
            "agent_manager.services.cross_repo_orchestrator.get_orchestration_file_path",
            return_value=Path(self.tmpdir.name) / "test_orchestration.json"
        )
        self.patcher.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.patcher.stop()
        self.tmpdir.cleanup()

    def test_detect_contract_files(self):
        files = [
            "agent_manager/api/routes/issues.py",
            "frontend/src/index.css",
            "docs/README.md",
            "agent_manager/models.py",
            "openapi.json",
        ]
        detected = detect_contract_files(files)
        self.assertIn("agent_manager/api/routes/issues.py", detected)
        self.assertIn("agent_manager/models.py", detected)
        self.assertIn("openapi.json", detected)
        self.assertNotIn("frontend/src/index.css", detected)

    def test_resolve_dependent_repos(self):
        deps = resolve_dependent_repos("BowenMichael/agent-manager")
        self.assertIn("BowenMichael/f1-frontend", deps)

        deps_empty = resolve_dependent_repos("Unknown/standalone_repo")
        self.assertEqual(deps_empty, [])

    def test_create_and_load_orchestration_plan(self):
        plan = create_orchestration_plan(
            initiator_repo="BowenMichael/agent-manager",
            initiator_issue=42,
            title="Update issues API schema",
            changed_files=["agent_manager/api/routes/issues.py"]
        )
        self.assertEqual(plan["status"], "ACTIVE")
        self.assertGreaterEqual(len(plan["child_tasks"]), 1)

        loaded = load_orchestration_plans()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["plan_id"], plan["plan_id"])

    def test_link_pull_requests_and_format_comment(self):
        plan = create_orchestration_plan(
            initiator_repo="BowenMichael/agent-manager",
            initiator_issue=10,
            title="Contract sync",
            changed_files=["agent_manager/api/routes/issues.py"]
        )
        plan_id = plan["plan_id"]
        child_repo = plan["dependent_repos"][0]

        updated = update_plan_pr_link(plan_id, parent_pr=100, child_repo=child_repo, child_pr=200)
        self.assertIsNotNone(updated)
        verified_child = [c for c in updated["child_tasks"] if c["child_repo"] == child_repo][0]
        self.assertEqual(verified_child["status"], "VERIFIED")
        self.assertEqual(verified_child["parent_pr_number"], 100)

        comment = format_cross_reference_comment("BowenMichael/agent-manager", 100, child_repo, 200)
        self.assertIn("Upstream PR", comment)
        self.assertIn("Downstream PR", comment)

    def test_evaluate_swarm_concurrency_with_orchestrator(self):
        s1 = MagicMock(repo="BowenMichael/agent-manager")
        s2 = MagicMock(repo="BowenMichael/fit-elo")
        s3 = MagicMock(repo="BowenMichael/full_swing_scraper")
        res = evaluate_swarm_concurrency([s1, s2, s3])
        self.assertEqual(res["score"], 100.0)
        self.assertTrue(res["per_repo_budget_caps"])
        self.assertTrue(res["cross_repo_coordination"])

    def test_api_orchestration_routes(self):
        create_res = self.client.post("/api/orchestration/plans", json={
            "initiator_repo": "BowenMichael/agent-manager",
            "initiator_issue": 55,
            "title": "API Contract Upgrade",
            "changed_files": ["agent_manager/api/routes/system.py"]
        })
        self.assertEqual(create_res.status_code, 200)
        plan_id = create_res.json()["plan"]["plan_id"]

        list_res = self.client.get("/api/orchestration/plans")
        self.assertEqual(list_res.status_code, 200)
        self.assertGreaterEqual(list_res.json()["count"], 1)

        link_res = self.client.post(f"/api/orchestration/plans/{plan_id}/link", json={
            "parent_pr_number": 115,
            "child_repo": "frontend",
            "child_pr_number": 5
        })
        self.assertEqual(link_res.status_code, 200)
        self.assertEqual(link_res.json()["status"], "linked")


if __name__ == "__main__":
    unittest.main()
