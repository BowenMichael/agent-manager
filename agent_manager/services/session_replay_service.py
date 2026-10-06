"""
Session Execution Replay & Visual Auditing Service.
Constructs lightweight, scrubbable execution trace artifacts from agent messages,
enabling step-by-step visual replay and terminal event inspection.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from agent_manager.models import AgentSessionInfo
from agent_manager.services.cost_calculator_service import calculate_session_cost

logger = logging.getLogger("agent_manager.services.session_replay")

REPLAYS_DIR = Path(__file__).resolve().parents[2] / "data" / "replays"


def get_replays_directory() -> Path:
    """Ensures replay storage directory exists."""
    REPLAYS_DIR.mkdir(parents=True, exist_ok=True)
    return REPLAYS_DIR


def build_session_replay(session: AgentSessionInfo) -> Dict[str, Any]:
    """Generates structured replay artifact from session messages and metadata."""
    frames = []
    messages = getattr(session, "messages", []) or []

    for idx, msg in enumerate(messages):
        role_val = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
        frames.append({
            "step": idx + 1,
            "id": msg.id,
            "role": role_val,
            "content": msg.content or "",
            "timestamp": msg.timestamp,
            "tool_name": msg.tool_name,
            "tool_args": msg.tool_args,
            "tool_output": msg.tool_output
        })

    cost_usd = calculate_session_cost(session)
    return {
        "session_id": session.session_id,
        "repo": session.repo,
        "issue_number": session.issue_number,
        "title": session.title,
        "status": session.status.value if hasattr(session.status, "value") else str(session.status),
        "started_at": session.started_at,
        "duration_seconds": getattr(session, "duration_seconds", 0.0) or 0.0,
        "total_tokens": getattr(session, "total_tokens", 0) or 0,
        "cost_usd": cost_usd,
        "total_frames": len(frames),
        "frames": frames
    }


def save_session_replay(session: AgentSessionInfo) -> Path:
    """Persists session replay artifact to disk for instant playback."""
    dir_path = get_replays_directory()
    replay_file = dir_path / f"{session.session_id}.replay.json"
    data = build_session_replay(session)
    try:
        replay_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.debug(f"Saved session replay for {session.session_id} to {replay_file}")
    except Exception as e:
        logger.warning(f"Failed to save session replay for {session.session_id}: {e}")
    return replay_file


def load_session_replay(session_id: str) -> Optional[Dict[str, Any]]:
    """Loads existing replay file or returns None if not found."""
    replay_file = get_replays_directory() / f"{session_id}.replay.json"
    if not replay_file.exists():
        return None
    try:
        return json.loads(replay_file.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Error loading replay file {replay_file}: {e}")
        return None
