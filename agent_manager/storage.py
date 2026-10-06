"""
Session and Settings Storage Manager.
Integrates relational database persistence with legacy JSON backup and settings storage.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
from agent_manager.models import AgentSessionInfo
from agent_manager.database import (
    init_db, save_session_record, load_session_records, get_session
)

logger = logging.getLogger("agent_manager.storage")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SESSIONS_FILE = DATA_DIR / "sessions.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

_DB_INITIALIZED = False


def _ensure_db_ready():
    """Lazily initializes relational database schema on first storage operation."""
    global _DB_INITIALIZED
    if not _DB_INITIALIZED:
        try:
            init_db()
            _DB_INITIALIZED = True
        except Exception as e:
            logger.warning(f"Database initialization warning in storage: {e}")


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
        for attempt in range(3):
            try:
                temp_file.replace(target_file)
                return
            except PermissionError:
                if attempt == 2:
                    raise
                time.sleep(0.05)
    except Exception as e:
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
    """Persists all agent sessions to the relational database and JSON backup."""
    _ensure_db_ready()
    try:
        for s in sessions.values():
            save_session_record(s)
        data = [s.model_dump() for s in sessions.values()]
        _atomic_write_json(get_storage_path(), data)
        logger.debug(f"Saved {len(sessions)} sessions to database and disk mirror.")
    except Exception as e:
        logger.error(f"Failed to persist sessions: {e}")


def save_single_session(session: AgentSessionInfo):
    """Safely updates or inserts a single session into database and disk mirror."""
    _ensure_db_ready()
    try:
        save_session_record(session)
        storage_file = get_storage_path()
        if storage_file.exists():
            try:
                with open(storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = []
        else:
            data = []

        serialized = session.model_dump()
        updated = False
        for idx, item in enumerate(data):
            if item.get("session_id") == session.session_id:
                data[idx] = serialized
                updated = True
                break
        if not updated:
            data.append(serialized)
        _atomic_write_json(storage_file, data)
        logger.debug(f"Saved single session {session.session_id} to database and mirror.")
    except Exception as e:
        logger.error(f"Failed to persist single session {session.session_id}: {e}")


def load_sessions() -> Dict[str, AgentSessionInfo]:
    """Loads all sessions from the relational database (falling back to JSON if needed)."""
    _ensure_db_ready()
    try:
        sessions = load_session_records()
        if sessions:
            return sessions
    except Exception as e:
        logger.error(f"Failed to load sessions from database: {e}")

    storage_file = get_storage_path()
    if not storage_file.exists():
        return {}

    try:
        with open(storage_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        sessions = {}
        for item in data:
            try:
                s = AgentSessionInfo(**item)
                sessions[s.session_id] = s
            except Exception:
                pass
        return sessions
    except Exception as e:
        logger.error(f"Failed to load sessions from disk fallback: {e}")
        return {}


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
            return data if isinstance(data, dict) else {}
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
