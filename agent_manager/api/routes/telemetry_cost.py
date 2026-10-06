"""
Telemetry Cost & Session Replay API Routes.
Exposes endpoints for fleet-wide spend metrics and structured session replays.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

from fastapi import APIRouter, HTTPException
from agent_manager.storage import load_sessions
from agent_manager.services.cost_calculator_service import generate_cost_telemetry_summary
from agent_manager.services.session_replay_service import build_session_replay, load_session_replay

router = APIRouter(prefix="/api", tags=["telemetry-cost"])


@router.get("/telemetry/cost-summary")
def get_cost_summary():
    """Returns aggregated real-time USD cost analytics and spend velocity."""
    sessions = list(load_sessions().values())
    return generate_cost_telemetry_summary(sessions)


@router.get("/sessions/{session_id}/replay")
def get_session_execution_replay(session_id: str):
    """Retrieves or builds the execution trace replay artifact for a given session."""
    cached_replay = load_session_replay(session_id)
    if cached_replay:
        return cached_replay

    sessions = load_sessions()
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return build_session_replay(session)
