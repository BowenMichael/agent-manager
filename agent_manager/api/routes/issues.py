"""
Unified Issue Management Route Aggregator.
Consolidates CRUD, agent actions, and voice creation endpoints.
Strictly adheres to Section 5 Anti-Monolith guidelines (< 50 lines).
"""

from fastapi import APIRouter
from agent_manager.api.routes.issues_crud import router as crud_router, IssueActionRequest, get_all_issues
from agent_manager.api.routes.issues_actions import router as actions_router
from agent_manager.api.routes.issues_voice import router as voice_router, VoiceIssueRequest

router = APIRouter(prefix="/api/issues", tags=["issues"])

@router.get("", include_in_schema=False)
async def get_all_issues_root():
    return await get_all_issues()

# Include modular sub-routers
router.include_router(crud_router)
router.include_router(actions_router)
router.include_router(voice_router)

__all__ = ["router", "IssueActionRequest", "VoiceIssueRequest"]

