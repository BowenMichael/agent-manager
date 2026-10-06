"""
Unit tests for Autonomous CVE & Library Upgrade Engine (Dependabot++).
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from fastapi import FastAPI

from agent_manager.runners.dependency_updater import (
    parse_pip_requirements,
    parse_package_json_dependencies,
    evaluate_vulnerability,
    audit_repository_manifests,
    generate_upgrade_plan,
    VulnerabilityReport
)
from agent_manager.api.routes.dependencies import router as dependencies_router


class TestDependencyUpdater(unittest.TestCase):
    """Test suite for dependency parsing, CVE auditing, and upgrade planning."""

    def test_parse_pip_requirements(self):
        """Verify requirements.txt parser extracts packages and version bounds."""
        req_content = "fastapi>=0.110.0\nuvicorn==0.30.0\n# comment\nrequests>=2.28.0\n"
        deps = parse_pip_requirements(req_content)
        self.assertEqual(deps.get("fastapi"), ">=0.110.0")
        self.assertEqual(deps.get("uvicorn"), "==0.30.0")
        self.assertEqual(deps.get("requests"), ">=2.28.0")

    def test_parse_package_json_dependencies(self):
        """Verify package.json parser merges dependencies and devDependencies."""
        pkg_json = '{"dependencies": {"react": "^18.2.0"}, "devDependencies": {"typescript": "^5.0.0"}}'
        deps = parse_package_json_dependencies(pkg_json)
        self.assertEqual(deps.get("react"), "^18.2.0")
        self.assertEqual(deps.get("typescript"), "^5.0.0")

    def test_evaluate_vulnerability(self):
        """Verify known vulnerable packages match advisory database."""
        vuln = evaluate_vulnerability("requests", "2.28.0", "requirements.txt")
        self.assertIsNotNone(vuln)
        self.assertEqual(vuln.cve_id, "CVE-2023-32681")
        self.assertEqual(vuln.ecosystem, "pip")

        safe = evaluate_vulnerability("unknown_safe_lib", "1.0.0", "requirements.txt")
        self.assertIsNone(safe)

    def test_audit_repository_manifests(self):
        """Verify file scanner audits temporary repository manifests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "requirements.txt").write_text("requests==2.28.0\nurllib3==1.26.5\n", encoding="utf-8")
            (tmppath / "package.json").write_text('{"dependencies": {"axios": "0.21.1"}}', encoding="utf-8")

            vulns = audit_repository_manifests(tmppath)
            pkg_names = [v.package_name for v in vulns]
            self.assertIn("requests", pkg_names)
            self.assertIn("urllib3", pkg_names)
            self.assertIn("axios", pkg_names)

    def test_generate_upgrade_plan(self):
        """Verify upgrade plan generation formats markdown prompt and branch name."""
        vulns = [
            VulnerabilityReport(
                package_name="requests",
                current_version="2.28.0",
                fixed_version=">=2.31.0",
                severity="medium",
                cve_id="CVE-2023-32681",
                manifest_file="requirements.txt",
                ecosystem="pip"
            )
        ]
        plan = generate_upgrade_plan("BowenMichael/agent-manager", vulns)
        self.assertEqual(plan.total_cves, 1)
        self.assertIn("feat/dependabot-upgrade-1-cves", plan.branch_name)
        self.assertIn("CVE-2023-32681", plan.instructions)
        self.assertIn("Instructions for Autonomous Upgrade Agent", plan.instructions)


class TestDependencyEndpoints(unittest.TestCase):
    """Test suite for /api/dependencies API routes."""

    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(dependencies_router)
        self.client = TestClient(self.app)

    def test_audit_endpoint(self):
        """Verify GET /api/dependencies/audit returns structured vulnerability list."""
        res = self.client.get("/api/dependencies/audit")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_vulnerabilities", data)
        self.assertIn("vulnerabilities", data)

    def test_plan_endpoint(self):
        """Verify POST /api/dependencies/plan generates actionable upgrade plan."""
        res = self.client.post("/api/dependencies/plan", json={"repo": "BowenMichael/test-repo"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["repo"], "BowenMichael/test-repo")
        self.assertIn("branch_name", data)
        self.assertIn("instructions", data)


if __name__ == "__main__":
    unittest.main()
