"""
Unit Tests for Healthz Endpoint, Dockerfile, and render.yaml Blueprint.
Validates liveness probe, multi-stage Docker build configuration, and Render IaC specification.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from agent_manager.server import app
from agent_manager.services.manifesto_metrics import evaluate_process_decoupling


class TestHealthzAndDeployment(unittest.TestCase):
    """Tests /healthz endpoint and cloud deployment artifacts."""

    def setUp(self):
        self.client = TestClient(app)
        self.root = Path(__file__).resolve().parents[1]

    def test_healthz_endpoint(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "agent-manager")
        self.assertEqual(data["database"], "connected")
        self.assertEqual(data["version"], "1.0.0")

    def test_dockerfile_structure(self):
        dockerfile_path = self.root / "Dockerfile"
        self.assertTrue(dockerfile_path.exists(), "Dockerfile must exist in repository root")
        content = dockerfile_path.read_text(encoding="utf-8")

        self.assertIn("FROM node:20-slim AS frontend-builder", content)
        self.assertIn("FROM python:3.11-slim AS runner", content)
        self.assertIn("USER appuser", content)
        self.assertIn("EXPOSE 8000", content)
        self.assertIn("HEALTHCHECK", content)
        self.assertIn("/healthz", content)
        self.assertIn("uvicorn agent_manager.server:app", content)

    def test_render_yaml_blueprint(self):
        render_path = self.root / "render.yaml"
        self.assertTrue(render_path.exists(), "render.yaml must exist in repository root")
        content = render_path.read_text(encoding="utf-8")

        self.assertIn("name: agent-manager-api", content)
        self.assertIn("healthCheckPath: /healthz", content)
        self.assertIn("dockerfilePath: ./Dockerfile", content)
        self.assertIn("name: agent-manager-redis", content)
        self.assertIn("name: agent-manager-db", content)
        self.assertIn("DATABASE_URL", content)

    def test_manifesto_process_decoupling_score(self):
        report = evaluate_process_decoupling()
        self.assertTrue(report["dockerized"])
        self.assertTrue(report["relational_db_migrated"])
        self.assertGreaterEqual(report["score"], 80.0)


if __name__ == "__main__":
    unittest.main()
