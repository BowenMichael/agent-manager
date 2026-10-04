import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any
from agent_manager.models import AgentSessionInfo, AgentStatus, ConversationMessage, MessageRole

logger = logging.getLogger("agent_manager.storage")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SESSIONS_FILE = DATA_DIR / "sessions.json"

def get_storage_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_FILE

def _atomic_write_json(target_file: Path, data: Any):
    """Atomically writes JSON to disk with retry and direct fallback for Windows file locks."""
    target_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file = target_file.with_suffix(f".tmp.{os.getpid()}_{int(time.time()*1000)}")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Retry atomic replace on Windows if file is briefly locked by reader
        for attempt in range(3):
            try:
                temp_file.replace(target_file)
                return
            except PermissionError:
                if attempt == 2:
                    raise
                time.sleep(0.05)
    except Exception as e:
        # Fallback to direct write if atomic replace repeatedly fails on Windows
        try:
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            raise e
    finally:
        if temp_file.exists():
            try:
                temp_file.unlink(missing_ok=True)
            except Exception:
                pass

def save_sessions(sessions: Dict[str, AgentSessionInfo]):
    """Persists all agent sessions to disk for task caching and durability."""
    try:
        storage_file = get_storage_path()
        data = [s.model_dump() for s in sessions.values()]
        _atomic_write_json(storage_file, data)
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


SETTINGS_FILE = DATA_DIR / "settings.json"

def get_settings_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return SETTINGS_FILE

def load_settings() -> dict:
    """Loads persistent settings from disk."""
    settings_file = get_settings_path()
    if not settings_file.exists():
        return {}
    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except Exception as e:
        logger.error(f"Failed to load settings from disk: {e}")
        return {}

def save_settings(settings: dict):
    """Persists settings to disk."""
    try:
        settings_file = get_settings_path()
        _atomic_write_json(settings_file, settings)
        logger.debug(f"Saved settings to {settings_file}")
    except Exception as e:
        logger.error(f"Failed to persist settings to disk: {e}")
        raise

