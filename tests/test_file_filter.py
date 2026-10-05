"""
Unit & Integration Tests for Long Generated File & Binary Filter Service.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC).
"""

import unittest
import tempfile
from pathlib import Path

from agent_manager.services.file_filter_service import (
    is_in_ignored_directory,
    is_generated_or_binary,
    is_file_too_large_for_inspection,
    filter_safe_source_files
)
from agent_manager.services.manifesto_metrics import evaluate_anti_monolith


class TestFileFilterService(unittest.TestCase):
    def test_is_in_ignored_directory(self):
        self.assertTrue(is_in_ignored_directory(Path("frontend/node_modules/react/index.js")))
        self.assertTrue(is_in_ignored_directory(Path(".worktrees/issue-1/code.py")))
        self.assertTrue(is_in_ignored_directory(Path("dist/assets/index.js")))
        self.assertFalse(is_in_ignored_directory(Path("agent_manager/server.py")))
        self.assertFalse(is_in_ignored_directory(Path("frontend/src/App.tsx")))

    def test_is_generated_or_binary_lockfiles(self):
        should_skip, reason = is_generated_or_binary("package-lock.json")
        self.assertTrue(should_skip)
        self.assertIn("lockfile", reason)

        should_skip, reason = is_generated_or_binary("pnpm-lock.yaml")
        self.assertTrue(should_skip)
        self.assertIn("lockfile", reason)

    def test_is_generated_or_binary_minified_and_media(self):
        self.assertTrue(is_generated_or_binary("vendor/bundle.min.js")[0])
        self.assertTrue(is_generated_or_binary("static/bundle.min.css")[0])
        self.assertTrue(is_generated_or_binary("assets/logo.png")[0])
        self.assertTrue(is_generated_or_binary("bundle.js.map")[0])

        # Normal source files must not be skipped
        self.assertFalse(is_generated_or_binary("agent_manager/models.py")[0])
        self.assertFalse(is_generated_or_binary("frontend/src/Header.tsx")[0])

    def test_is_file_too_large_for_inspection(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".py") as tmp:
            tmp.write("\n".join(f"# Line {i}" for i in range(300)))
            tmp_path = Path(tmp.name)

        try:
            too_large, reason = is_file_too_large_for_inspection(tmp_path, max_lines=250)
            self.assertTrue(too_large)
            self.assertIn("exceeding safe limit", reason)

            # High threshold check
            too_large, _ = is_file_too_large_for_inspection(tmp_path, max_lines=500)
            self.assertFalse(too_large)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_filter_safe_source_files(self):
        candidates = [
            "src/index.ts",
            "package-lock.json",
            "dist/bundle.js",
            "src/components/Header.tsx",
            "public/favicon.ico",
            "node_modules/axios/index.js"
        ]
        safe = filter_safe_source_files(candidates)
        self.assertEqual(len(safe), 2)
        self.assertIn("src/index.ts", safe)
        self.assertIn("src/components/Header.tsx", safe)

    def test_manifesto_pillar_three_integration(self):
        res = evaluate_anti_monolith()
        self.assertTrue(res["long_file_filter_active"])
        self.assertGreaterEqual(res["score"], 40.0)


if __name__ == "__main__":
    unittest.main()
