"""
Unit & Integration Tests for Manifesto Compliance Metrics.
Verifies quantitative assertions across all Eight Pillars of the Agent Manager Manifesto.
Adheres strictly to Anti-Monolith guidelines (< 250 lines).
"""

import unittest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from agent_manager.server import app
from agent_manager.services.manifesto_metrics import (
    evaluate_observability,
    evaluate_isolation,
    evaluate_anti_monolith,
    evaluate_process_decoupling,
    evaluate_cognitive_pipeline,
    evaluate_swarm_concurrency,
    evaluate_ubiquitous_command,
    evaluate_accountability,
    generate_manifesto_compliance_report,
)


class TestManifestoMetrics(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_pillar_i_observability_metric(self):
        sess1 = MagicMock(total_tokens=1500, messages=[{"role": "USER"}, {"role": "AGENT"}])
        sess2 = MagicMock(total_tokens=0, messages=[])
        telemetry = [{"session_id": f"s{i}", "total_tokens": 100} for i in range(60)]

        res = evaluate_observability([sess1, sess2], telemetry)
        self.assertIn("score", res)
        self.assertGreater(res["score"], 0.0)
        self.assertEqual(res["token_tracking_active"], 0.5)

    def test_pillar_ii_isolation_metric(self):
        s_isolated = MagicMock(session_id="s1", worktree_path="e:/repo/.worktrees/issue-42")
        s_unisolated = MagicMock(session_id="s2", worktree_path="e:/repo/main")

        res = evaluate_isolation([s_isolated, s_unisolated])
        self.assertIn("score", res)
        self.assertEqual(res["isolated_sessions_ratio"], 0.5)

    def test_pillar_iii_anti_monolith_metric(self):
        res = evaluate_anti_monolith()
        self.assertIn("score", res)
        self.assertIn("semantic_cross_repo_memory", res)

    def test_pillar_iv_process_decoupling_metric(self):
        res = evaluate_process_decoupling()
        self.assertIn("score", res)
        self.assertTrue(res["detached_daemon"])

    def test_pillar_v_cognitive_pipeline_metric(self):
        res = evaluate_cognitive_pipeline()
        self.assertIn("score", res)
        self.assertTrue(res["interpretation_service"])

    def test_pillar_vi_swarm_concurrency_metric(self):
        s1 = MagicMock(repo="BowenMichael/f1-frontend")
        s2 = MagicMock(repo="BowenMichael/agent-manager")
        s3 = MagicMock(repo="BowenMichael/fit-elo")

        res = evaluate_swarm_concurrency([s1, s2, s3])
        self.assertIn("score", res)
        self.assertEqual(res["monitored_repositories"], 3)

    def test_pillar_vii_ubiquitous_command_metric(self):
        res = evaluate_ubiquitous_command()
        self.assertIn("score", res)
        self.assertTrue(res["desktop_react"])
        self.assertTrue(res["voice_intake"])

    def test_pillar_viii_accountability_metric(self):
        res = evaluate_accountability()
        self.assertIn("score", res)
        self.assertTrue(res["changelog_present"])

    def test_full_compliance_report_and_api(self):
        report = generate_manifesto_compliance_report()
        self.assertIn("manifesto_health_index", report)
        self.assertIn("grade", report)
        self.assertIn("pillars", report)
        self.assertEqual(len(report["pillars"]), 8)
        # Health index reflects growing multi-pillar enterprise compliance
        self.assertGreater(report["manifesto_health_index"], 0.0)
        self.assertLessEqual(report["manifesto_health_index"], 100.0)

        response = self.client.get("/api/telemetry/manifesto-metrics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("manifesto_health_index", data)
        self.assertEqual(data["grade"], report["grade"])


if __name__ == "__main__":
    unittest.main()
