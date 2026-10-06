"""
Ephemeral Preview API Endpoints.
Provides REST controls for launching, stopping, and validating preview environments.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

from pathlib import Path
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from agent_manager.services.preview_env_service import (
    launch_preview_server, stop_preview_server, list_active_previews
)
from agent_manager.runners.preview import run_preview_validation

router = APIRouter(prefix="/api/previews", tags=["previews"])


class PreviewLaunchRequest(BaseModel):
    session_id: str
    worktree_path: str


class PreviewStopRequest(BaseModel):
    session_id: str


@router.get("/active")
def get_active_previews():
    """Lists all currently running ephemeral preview environments."""
    return {"active_previews": list_active_previews()}


@router.post("/launch")
def launch_preview(req: PreviewLaunchRequest):
    """Launches an ephemeral preview server for a worktree."""
    wt_path = Path(req.worktree_path)
    if not wt_path.exists():
        raise HTTPException(status_code=400, detail=f"Worktree path {req.worktree_path} not found")

    instance = launch_preview_server(req.session_id, wt_path)
    return {
        "status": instance.status,
        "preview_url": instance.url,
        "port": instance.port,
        "pid": instance.pid
    }


@router.post("/stop")
def stop_preview(req: PreviewStopRequest):
    """Terminates an active preview server."""
    success = stop_preview_server(req.session_id)
    return {"session_id": req.session_id, "stopped": success}


@router.post("/validate")
def validate_preview(req: PreviewLaunchRequest):
    """Runs full automated visual smoke validation against worktree preview."""
    wt_path = Path(req.worktree_path)
    if not wt_path.exists():
        raise HTTPException(status_code=400, detail=f"Worktree path {req.worktree_path} not found")

    result = run_preview_validation(req.session_id, wt_path, auto_teardown=True)
    return result
