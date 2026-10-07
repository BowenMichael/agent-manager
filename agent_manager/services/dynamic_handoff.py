"""
Dynamic Cognitive Model Handoff Controller.
Manages multi-model division of labor across autonomous stages (Triage -> Architect -> Executor -> Reviewer).
Dynamically escalates reasoning models and effort levels based on task complexity and error rates.
Adheres strictly to Anti-Monolith guidelines (< 250 lines, < 40 lines per function).
"""

from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from agent_manager.config import DEFAULT_MODEL, DEFAULT_EFFORT


class CognitiveStage(str, Enum):
    """Four-stage cognitive pipeline for autonomous engineering."""
    STAGE_1_TRIAGE = "triage"
    STAGE_2_ARCHITECT = "architect"
    STAGE_3_EXECUTOR = "executor"
    STAGE_4_REVIEWER = "reviewer"


class StageModelConfig(BaseModel):
    """Model selection and effort parameters for a specific stage."""
    stage: CognitiveStage
    model: str
    effort: str = "low"  # low, medium, high
    max_turns: int = 15
    escalated: bool = False
    reason: Optional[str] = None


class DynamicHandoffController:
    """Orchestrates model selection and handoffs across autonomous stages."""

    DEFAULT_STAGE_MODELS: Dict[CognitiveStage, tuple[str, str]] = {
        CognitiveStage.STAGE_1_TRIAGE: ("gemini-2.5-flash", "low"),
        CognitiveStage.STAGE_2_ARCHITECT: ("gemini-2.5-flash", "high"),
        CognitiveStage.STAGE_3_EXECUTOR: ("gemini-2.5-flash", "high"),
        CognitiveStage.STAGE_4_REVIEWER: ("gemini-2.5-pro", "high"),
    }

    def get_stage_config(
        self,
        stage: CognitiveStage,
        error_streak: int = 0,
        complexity_score: float = 1.0,
        repo: Optional[str] = None
    ) -> StageModelConfig:
        """Determines model and effort tier, applying escalation when necessary."""
        base_model, base_effort = self.DEFAULT_STAGE_MODELS.get(
            stage, (DEFAULT_MODEL, DEFAULT_EFFORT)
        )
        
        # Check for model escalation conditions
        if error_streak >= 2 or complexity_score > 3.0:
            return self._create_escalated_config(stage, error_streak, complexity_score)

        return StageModelConfig(
            stage=stage,
            model=base_model,
            effort=base_effort,
            escalated=False
        )

    def _create_escalated_config(
        self,
        stage: CognitiveStage,
        error_streak: int,
        complexity: float
    ) -> StageModelConfig:
        """Escalates reasoning model to Pro tier on high complexity or repeated faults."""
        reason = f"Escalated due to error_streak={error_streak}" if error_streak >= 2 else f"High complexity={complexity}"
        return StageModelConfig(
            stage=stage,
            model="gemini-2.5-pro",
            effort="high",
            escalated=True,
            reason=reason
        )

    def determine_next_stage(
        self,
        current_stage: CognitiveStage,
        success: bool,
        has_blockers: bool = False
    ) -> Optional[CognitiveStage]:
        """Calculates state transition to the next cognitive stage."""
        if not success:
            return None

        transitions = {
            CognitiveStage.STAGE_1_TRIAGE: CognitiveStage.STAGE_2_ARCHITECT,
            CognitiveStage.STAGE_2_ARCHITECT: CognitiveStage.STAGE_3_EXECUTOR,
            CognitiveStage.STAGE_3_EXECUTOR: CognitiveStage.STAGE_4_REVIEWER,
            CognitiveStage.STAGE_4_REVIEWER: None  # Pipeline finished
        }
        
        if current_stage == CognitiveStage.STAGE_4_REVIEWER and has_blockers:
            # Re-queue back to executor if reviewer finds critical security/AST blockers
            return CognitiveStage.STAGE_3_EXECUTOR

        return transitions.get(current_stage)


# Global singleton handoff controller
handoff_controller = DynamicHandoffController()
