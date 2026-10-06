"""
Unit Tests for Release Manager & SemVer Release Tagging Engine.
Validates conventional commit parsing, semantic version calculation, release notes formatting, and tag creation.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent_manager.runners.release_manager import (
    parse_conventional_commits, bump_semver, get_project_version,
    update_version_manifest, generate_release_notes, create_annotated_git_tag
)
from agent_manager.services.manifesto_metrics import evaluate_accountability


class TestReleaseManager(unittest.TestCase):
    """Tests for conventional commits and automated SemVer releases."""

    def test_parse_conventional_commits_bumps(self):
        # Test minor bump from features
        res_minor = parse_conventional_commits(["feat: add vector memory (#92)", "fix: fix bug (#1)"])
        self.assertEqual(res_minor["recommended_bump"], "minor")
        self.assertEqual(len(res_minor["features"]), 1)

        # Test major bump from breaking change
        res_major = parse_conventional_commits(["feat!: drop support for python 3.9", "fix: login"])
        self.assertEqual(res_major["recommended_bump"], "major")
        self.assertEqual(len(res_major["breaking"]), 1)

        # Test patch bump from fixes only
        res_patch = parse_conventional_commits(["fix: correct typo in route", "docs: update readme"])
        self.assertEqual(res_patch["recommended_bump"], "patch")

    def test_bump_semver_math(self):
        self.assertEqual(bump_semver("1.2.3", "patch"), "1.2.4")
        self.assertEqual(bump_semver("1.2.3", "minor"), "1.3.0")
        self.assertEqual(bump_semver("1.2.3", "major"), "2.0.0")
        self.assertEqual(bump_semver("v2.5.9", "patch"), "2.5.10")

    def test_manifest_version_update(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            pkg = p / "package.json"
            pkg.write_text(json.dumps({"name": "app", "version": "1.0.0"}), encoding="utf-8")

            self.assertEqual(get_project_version(p), "1.0.0")
            success = update_version_manifest(p, "1.1.0")
            self.assertTrue(success)
            self.assertEqual(get_project_version(p), "1.1.0")

    def test_generate_release_notes(self):
        parsed = {
            "breaking": ["feat!: dropped legacy JSON store"],
            "features": ["feat(rag): added vector memory"],
            "fixes": ["fix: resolved rebase loop"],
            "others": ["docs: updated prompt"],
        }
        notes = generate_release_notes("1.2.0", parsed)
        self.assertIn("## Release v1.2.0", notes)
        self.assertIn("Breaking Changes", notes)
        self.assertIn("New Features", notes)
        self.assertIn("Bug Fixes", notes)

    @patch("agent_manager.runners.release_manager.subprocess.run")
    def test_create_annotated_git_tag(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            res = create_annotated_git_tag(p, "1.2.0", "Release 1.2.0")
            self.assertTrue(res)
            mock_run.assert_called_with(["git", "tag", "-a", "v1.2.0", "-m", "Release 1.2.0"], cwd=str(p), capture_output=True, text=True, timeout=10)

    def test_evaluate_accountability_score(self):
        report = evaluate_accountability()
        self.assertTrue(report["semver_release_engine"])
        self.assertTrue(report["ephemeral_preview_active"])
        self.assertGreaterEqual(report["score"], 65.0)


if __name__ == "__main__":
    unittest.main()
