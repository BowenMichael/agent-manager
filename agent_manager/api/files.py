import logging
import subprocess
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from agent_manager.runner import AgentRunnerManager

logger = logging.getLogger("agent_manager.api.files")

router = APIRouter(prefix="/api/agents", tags=["files"])


def _get_secure_base_dir(session_id: str) -> Path:
    """Retrieve and validate the worktree or root base directory for an agent session."""
    runner = AgentRunnerManager()
    session = runner.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent session '{session_id}' not found."
        )

    base_path_str = session.worktree_path
    if not base_path_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session has no active worktree directory configured."
        )

    base_dir = Path(base_path_str).resolve()
    if not base_dir.exists() or not base_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session worktree directory does not exist on disk."
        )

    return base_dir


def _resolve_secure_file_path(base_dir: Path, requested_path: str) -> Path:
    """Safely resolve requested path and prevent path traversal outside base_dir."""
    cleaned = requested_path.strip().strip("'\"")
    raw_path = Path(cleaned)

    if raw_path.is_absolute():
        resolved = raw_path.resolve()
    else:
        resolved = (base_dir / raw_path).resolve()

    try:
        resolved.relative_to(base_dir)
    except ValueError:
        logger.warning(f"Path traversal blocked: '{requested_path}' outside '{base_dir}'")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Path traverses outside session worktree directory."
        )

    return resolved


@router.get("/{session_id}/files/content")
async def get_session_file_content(
    session_id: str,
    path: str = Query(..., description="File path relative to worktree or absolute within worktree")
):
    """Securely fetch text content of a file within the session worktree."""
    base_dir = _get_secure_base_dir(session_id)
    target_file = _resolve_secure_file_path(base_dir, path)

    if not target_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {path}"
        )

    if target_file.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target path is a directory, not a file: {path}"
        )

    # Prevent reading excessively large files (> 2MB)
    file_size = target_file.stat().st_size
    if file_size > 2 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File is too large to view directly ({file_size} bytes)."
        )

    try:
        content = target_file.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.error(f"Error reading file '{target_file}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file: {str(e)}"
        )

    rel_path = str(target_file.relative_to(base_dir)).replace("\\", "/")
    return {
        "session_id": session_id,
        "path": rel_path,
        "filename": target_file.name,
        "size": file_size,
        "lines": content.count("\n") + (1 if content else 0),
        "content": content
    }


@router.get("/{session_id}/files/diff")
async def get_session_file_diff(
    session_id: str,
    path: Optional[str] = Query(None, description="Optional path to scope git diff")
):
    """Return git diff for a file or the entire session worktree against HEAD."""
    base_dir = _get_secure_base_dir(session_id)
    cmd = ["git", "diff", "HEAD"]

    if path:
        target_file = _resolve_secure_file_path(base_dir, path)
        rel_path = str(target_file.relative_to(base_dir))
        cmd.extend(["--", rel_path])

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(base_dir),
            capture_output=True,
            text=True,
            timeout=10
        )
        diff_text = proc.stdout
    except Exception as e:
        logger.error(f"Error executing git diff in '{base_dir}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute git diff: {str(e)}"
        )

    return {
        "session_id": session_id,
        "path": path,
        "diff": diff_text
    }
