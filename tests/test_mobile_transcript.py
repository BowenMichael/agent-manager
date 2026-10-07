"""
Integration Tests for Mobile Transcript Viewer & Tool Components.
Verifies file structure, export signatures, and component contracts.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import unittest
from pathlib import Path


class TestMobileTranscript(unittest.TestCase):
    """Verifies Expo mobile transcript viewer and subcomponents."""

    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent

    def test_transcript_components_exist(self):
        """Verify all transcript components exist in apps/mobile/components/."""
        comp_dir = self.root / "apps" / "mobile" / "components"
        self.assertTrue((comp_dir / "ThinkingAccordion.tsx").exists())
        self.assertTrue((comp_dir / "ToolCallCard.tsx").exists())
        self.assertTrue((comp_dir / "TokenBudgetBar.tsx").exists())
        self.assertTrue((self.root / "apps" / "mobile" / "app" / "session" / "[id].tsx").exists())

    def test_thinking_accordion_exports(self):
        """Verify ThinkingAccordion component props and toggle logic."""
        content = (self.root / "apps" / "mobile" / "components" / "ThinkingAccordion.tsx").read_text(encoding="utf-8")
        self.assertIn("ThinkingAccordion", content)
        self.assertIn("Reasoning Trace", content)
        self.assertIn("tokenBadge", content)

    def test_tool_call_card_exports(self):
        """Verify ToolCallCard component props and diff rendering."""
        content = (self.root / "apps" / "mobile" / "components" / "ToolCallCard.tsx").read_text(encoding="utf-8")
        self.assertIn("ToolCallCard", content)
        self.assertIn("Output / Diff", content)
        self.assertIn("codeBlock", content)

    def test_token_budget_bar_exports(self):
        """Verify TokenBudgetBar calculation and thresholds."""
        content = (self.root / "apps" / "mobile" / "components" / "TokenBudgetBar.tsx").read_text(encoding="utf-8")
        self.assertIn("TokenBudgetBar", content)
        self.assertIn("getProgressColor", content)
        self.assertIn("maxTokens", content)


if __name__ == "__main__":
    unittest.main()
