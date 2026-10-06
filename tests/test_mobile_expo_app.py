"""
Unit Tests for Expo Mobile App Scaffolding.
Validates app.json configuration, Expo Router file structure, theme tokens,
environment variables, and Manifesto Pillar VII metrics integration.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import json
import unittest
from pathlib import Path

from agent_manager.services.manifesto_metrics import evaluate_ubiquitous_command


class TestExpoMobileScaffold(unittest.TestCase):
    """Test suite for the cross-platform Expo mobile and web client."""

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.mobile_root = self.repo_root / "apps" / "mobile"

    def test_app_json_configuration(self):
        app_json_path = self.mobile_root / "app.json"
        self.assertTrue(app_json_path.exists(), "apps/mobile/app.json must exist")

        config = json.loads(app_json_path.read_text(encoding="utf-8"))
        expo_cfg = config.get("expo", {})
        self.assertEqual(expo_cfg.get("name"), "Agent Manager")
        self.assertEqual(expo_cfg.get("slug"), "agent-manager")
        self.assertIn("web", expo_cfg)
        self.assertEqual(expo_cfg["web"].get("bundler"), "metro")

    def test_package_json_dependencies(self):
        pkg_path = self.mobile_root / "package.json"
        self.assertTrue(pkg_path.exists(), "apps/mobile/package.json must exist")

        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        deps = pkg.get("dependencies", {})
        self.assertIn("expo", deps)
        self.assertIn("expo-router", deps)
        self.assertIn("react", deps)
        self.assertIn("react-native", deps)

        scripts = pkg.get("scripts", {})
        self.assertIn("start", scripts)
        self.assertIn("web", scripts)

    def test_expo_router_screen_hierarchy(self):
        app_dir = self.mobile_root / "app"
        self.assertTrue((app_dir / "_layout.tsx").exists(), "Root layout must exist")
        self.assertTrue((app_dir / "index.tsx").exists(), "Sessions list screen must exist")
        self.assertTrue((app_dir / "session" / "[id].tsx").exists(), "Session detail screen must exist")
        self.assertTrue((app_dir / "settings.tsx").exists(), "Settings screen must exist")

    def test_theme_and_environment_constants(self):
        theme_file = self.mobile_root / "constants" / "Theme.ts"
        config_file = self.mobile_root / "constants" / "Config.ts"
        self.assertTrue(theme_file.exists(), "Theme constants must exist")
        self.assertTrue(config_file.exists(), "Config constants must exist")

        theme_content = theme_file.read_text(encoding="utf-8")
        self.assertIn("Colors", theme_content)
        self.assertIn("dark", theme_content)

        config_content = config_file.read_text(encoding="utf-8")
        self.assertIn("EXPO_PUBLIC_API_URL", config_content)

    def test_manifesto_pillar_vii_evaluation(self):
        res = evaluate_ubiquitous_command()
        self.assertTrue(res["mobile_expo"], "Manifesto metrics must detect mobile Expo app")
        self.assertGreaterEqual(res["score"], 50.0, "Pillar VII score must reach at least 50.0")


if __name__ == "__main__":
    unittest.main()
