import json
import logging
from pathlib import Path
from typing import Dict
from agent_manager.models import AgentSessionInfo, AgentStatus, ConversationMessage, MessageRole

logger = logging.getLogger("agent_manager.storage")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SESSIONS_FILE = DATA_DIR / "sessions.json"

def get_storage_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_FILE

def save_sessions(sessions: Dict[str, AgentSessionInfo]):
    """Persists all agent sessions to disk for task caching and durability."""
    try:
        storage_file = get_storage_path()
        data = [s.model_dump() for s in sessions.values()]
        temp_file = storage_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_file.replace(storage_file)
        logger.debug(f"Saved {len(sessions)} sessions to {storage_file}")
    except Exception as e:
        logger.error(f"Failed to persist sessions to disk: {e}")

def load_sessions() -> Dict[str, AgentSessionInfo]:
    """Loads cached sessions from disk on application startup."""
    storage_file = get_storage_path()
    if not storage_file.exists():
        logger.info(f"No existing sessions cache found at {storage_file}. Starting fresh.")
        return {}

    try:
        with open(storage_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        sessions: Dict[str, AgentSessionInfo] = {}
        for item in data:
            try:
                session = AgentSessionInfo(**item)
                # If server restarted while agent was running, recover cleanly to IN_REVIEW/IDLE
                if session.status in [AgentStatus.RUNNING, AgentStatus.INITIALIZING]:
                    session.status = AgentStatus.IN_REVIEW
                    session.messages.append(
                        ConversationMessage(
                            id=f"restore-{len(session.messages)}",
                            role=MessageRole.SYSTEM,
                            content="🔄 [Task Cache Restored] Agent session reloaded from disk cache. Chat remains active and ready for input or review."
                        )
                    )
                sessions[session.session_id] = session
            except Exception as item_err:
                logger.warning(f"Error parsing cached session item: {item_err}")

        logger.info(f"Loaded {len(sessions)} cached agent sessions from {storage_file}")
        return sessions
    except Exception as e:
        logger.error(f"Failed to load cached sessions from disk: {e}")
        return {}
