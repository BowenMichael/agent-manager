"""
Unit tests for agent comment formatting and identification utilities.
"""
import unittest

from agent_manager.formatters.comments import (
    format_agent_comment,
    format_agent_metadata_footer,
    is_agent_comment,
    BADGE_AUTONOMOUS_AGENT,
    BADGE_AGENT_UPDATE,
    BADGE_AGENT_TAKEOVER,
    BADGE_AGENT_PAUSED,
    FOOTER_SIGNATURE,
)


class TestAgentCommentFormatters(unittest.TestCase):
    def test_metadata_footer_all_fields(self):
        footer = format_agent_metadata_footer(
            session_id="issue-7-abc",
            worktree_path=".worktrees/issue-7",
            git_branch="feat/issue-7"
        )
        self.assertIn(FOOTER_SIGNATURE, footer)
        self.assertIn("Session: `issue-7-abc`", footer)
        self.assertIn("Branch: `feat/issue-7`", footer)
        self.assertIn("Worktree: `.worktrees/issue-7`", footer)
        self.assertTrue(footer.startswith("\n\n---\n*"))
        self.assertTrue(footer.endswith("*"))

    def test_metadata_footer_empty_fields(self):
        footer = format_agent_metadata_footer()
        self.assertIn(FOOTER_SIGNATURE, footer)
        self.assertEqual(footer, f"\n\n---\n*{FOOTER_SIGNATURE}*")

    def test_format_agent_comment_default_header(self):
        comment = format_agent_comment(
            body="Implemented the core fix and ran tests.",
            session_id="session-123"
        )
        self.assertTrue(comment.startswith(BADGE_AUTONOMOUS_AGENT))
        self.assertIn("Implemented the core fix and ran tests.", comment)
        self.assertIn(FOOTER_SIGNATURE, comment)
        self.assertIn("Session: `session-123`", comment)

    def test_format_agent_comment_custom_header(self):
        comment = format_agent_comment(
            body="Reviewing the requirements now.",
            header=BADGE_AGENT_TAKEOVER,
            session_id="sess-takeover",
            git_branch="feat/issue-7",
            worktree_path=".worktrees/issue-7"
        )
        self.assertTrue(comment.startswith(BADGE_AGENT_TAKEOVER))
        self.assertIn("Reviewing the requirements now.", comment)
        self.assertIn(FOOTER_SIGNATURE, comment)
        self.assertIn("Branch: `feat/issue-7`", comment)

    def test_format_agent_comment_avoids_duplicate_badge(self):
        body_with_badge = f"{BADGE_AGENT_UPDATE}\n\nTask progress completed successfully."
        comment = format_agent_comment(
            body=body_with_badge,
            session_id="sess-no-dup"
        )
        # Should not prepend another BADGE_AUTONOMOUS_AGENT
        self.assertFalse(comment.startswith(f"{BADGE_AUTONOMOUS_AGENT}\n\n{BADGE_AGENT_UPDATE}"))
        self.assertTrue(comment.startswith(BADGE_AGENT_UPDATE))
        self.assertIn(FOOTER_SIGNATURE, comment)

    def test_is_agent_comment_detection(self):
        # Empty or None cases
        self.assertFalse(is_agent_comment(None))
        self.assertFalse(is_agent_comment(""))
        self.assertFalse(is_agent_comment("   "))

        # Developer human comments
        self.assertFalse(is_agent_comment("Can you please check the styling on mobile?"))
        self.assertFalse(is_agent_comment("Looks great! Ready to merge."))

        # Agent header badges
        self.assertTrue(is_agent_comment(f"{BADGE_AUTONOMOUS_AGENT}\n\nAgent started."))
        self.assertTrue(is_agent_comment(f"{BADGE_AGENT_UPDATE}\n\nStatus update."))
        self.assertTrue(is_agent_comment(f"{BADGE_AGENT_TAKEOVER}\n\nTaking over."))
        self.assertTrue(is_agent_comment(f"{BADGE_AGENT_PAUSED}\n\nPaused execution."))

        # Task completion badge
        self.assertTrue(is_agent_comment("🚀 **Task Completed**\n\nAll tasks done."))

        # Circuit breaker / pause notices
        self.assertTrue(is_agent_comment("⚠️ **Task Paused: Circuit Breaker Triggered**\n\nDetails"))
        self.assertTrue(is_agent_comment("### 🛑 Repetitive Tool Loop Detected\n- Tool: view_file"))
        self.assertTrue(is_agent_comment("### 📊 Task Insights\n- Turns Completed: 15 / 15"))

        # Footer signature detection
        self.assertTrue(is_agent_comment(f"Any custom comment body\n\n---\n*{FOOTER_SIGNATURE} | Session: `123`*"))


if __name__ == "__main__":
    unittest.main()
