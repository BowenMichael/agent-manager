"""
Feedback Ingestion API Routes.
Exposes POST /api/feedback/submit for web and mobile client telemetry.
Adheres strictly to Section 5 Anti-Monolith guidelines (< 50 LOC).
"""

import logging
from fastapi import APIRouter, HTTPException, status
from agent_manager.services.feedback_service import (
    FeedbackSubmissionRequest,
    ingest_feedback
)

logger = logging.getLogger("agent_manager.api.routes.feedback")
router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("/submit", status_code=status.HTTP_201_CREATED)
async def submit_feedback(req: FeedbackSubmissionRequest):
    """
    Ingests bug report, UI feedback, or feature request from client apps or Expo mobile,
    creates a structured GitHub issue, and places it into Project Board 'Ready for Agent'.
    """
    try:
        result = await ingest_feedback(req)
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=result.get("error", "Failed to ingest feedback to GitHub")
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error handling feedback submission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal feedback processor error: {str(e)}"
        )


__all__ = ["router", "FeedbackSubmissionRequest"]
