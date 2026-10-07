"""
Unit Tests for Dynamic Cognitive Model Handoff Controller.
Tests model tier selection, error-streak escalation, and multi-stage lifecycle transitions.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import unittest
from agent_manager.services.dynamic_handoff import (
    DynamicHandoffController,
    CognitiveStage,
    StageModelConfig,
    handoff_controller,
)


class TestDynamicHandoffController(unittest.TestCase):
    """Test suite for multi-model cognitive handoffs and escalations."""

    def setUp(self):
        self.controller = DynamicHandoffController()

    def test_default_stage_model_selection(self):
        """Verify standard model tiers across all 4 cognitive stages."""
        triage_cfg = self.controller.get_stage_config(CognitiveStage.STAGE_1_TRIAGE)
        self.assertEqual(triage_cfg.model, "gemini-2.5-flash")
        self.assertEqual(triage_cfg.effort, "low")
        self.assertFalse(triage_cfg.escalated)

        arch_cfg = self.controller.get_stage_config(CognitiveStage.STAGE_2_ARCHITECT)
        self.assertEqual(arch_cfg.model, "gemini-2.5-flash")
        self.assertEqual(arch_cfg.effort, "high")

        exec_cfg = self.controller.get_stage_config(CognitiveStage.STAGE_3_EXECUTOR)
        self.assertEqual(exec_cfg.model, "gemini-2.5-flash")
        self.assertEqual(exec_cfg.effort, "high")

        rev_cfg = self.controller.get_stage_config(CognitiveStage.STAGE_4_REVIEWER)
        self.assertEqual(rev_cfg.model, "gemini-2.5-pro")
        self.assertEqual(rev_cfg.effort, "high")

    def test_escalation_on_error_streak(self):
        """Verify escalation to Pro tier when agent encounters repeated errors."""
        cfg = self.controller.get_stage_config(
            CognitiveStage.STAGE_3_EXECUTOR,
            error_streak=2
        )
        self.assertTrue(cfg.escalated)
        self.assertEqual(cfg.model, "gemini-2.5-pro")
        self.assertEqual(cfg.effort, "high")
        self.assertIn("error_streak=2", cfg.reason)

    def test_escalation_on_high_complexity(self):
        """Verify escalation on high complexity score."""
        cfg = self.controller.get_stage_config(
            CognitiveStage.STAGE_2_ARCHITECT,
            complexity_score=4.5
        )
        self.assertTrue(cfg.escalated)
        self.assertEqual(cfg.model, "gemini-2.5-pro")
        self.assertIn("High complexity=4.5", cfg.reason)

    def test_stage_lifecycle_transitions(self):
        """Verify sequential stage progression from Triage to Reviewer."""
        next_s2 = self.controller.determine_next_stage(CognitiveStage.STAGE_1_TRIAGE, success=True)
        self.assertEqual(next_s2, CognitiveStage.STAGE_2_ARCHITECT)

        next_s3 = self.controller.determine_next_stage(CognitiveStage.STAGE_2_ARCHITECT, success=True)
        self.assertEqual(next_s3, CognitiveStage.STAGE_3_EXECUTOR)

        next_s4 = self.controller.determine_next_stage(CognitiveStage.STAGE_3_EXECUTOR, success=True)
        self.assertEqual(next_s4, CognitiveStage.STAGE_4_REVIEWER)

        next_done = self.controller.determine_next_stage(CognitiveStage.STAGE_4_REVIEWER, success=True)
        self.assertIsNone(next_done)

    def test_reviewer_blocker_requeue(self):
        """Verify reviewer findings re-route task back to executor."""
        requeued = self.controller.determine_next_stage(
            CognitiveStage.STAGE_4_REVIEWER,
            success=True,
            has_blockers=True
        )
        self.assertEqual(requeued, CognitiveStage.STAGE_3_EXECUTOR)


if __name__ == "__main__":
    unittest.main()
