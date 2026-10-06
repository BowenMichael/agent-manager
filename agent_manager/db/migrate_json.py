"""
Automatic Migration from Legacy Flat JSON to Relational Database.
Migrates historical sessions from sessions.json on startup without data loss.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import json
import logging
from pathlib import Path
from typing import Optional
from agent_manager.models import AgentSessionInfo
from agent_manager.db.repository import save_session, get_session

logger = logging.getLogger("agent_manager.db.migrate_json")


def _read_legacy_file(json_file: Path) -> list:
    """Safely reads and parses the legacy JSON file."""
    if not json_file.exists():
        return []
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"Could not read legacy sessions JSON at {json_file}: {e}")
        return []


def migrate_json_to_database(json_path: Optional[Path] = None) -> int:
    """Migrates sessions from sessions.json into the relational database if not present."""
    if json_path is None:
        data_dir = Path(__file__).resolve().parents[2] / "data"
        json_path = data_dir / "sessions.json"

    raw_items = _read_legacy_file(json_path)
    if not raw_items:
        return 0

    migrated_count = 0
    for item in raw_items:
        try:
            info = AgentSessionInfo(**item)
            existing = get_session(info.session_id)
            if not existing:
                save_session(info)
                migrated_count += 1
        except Exception as e:
            logger.warning(f"Skipping malformed legacy session {item.get('session_id')}: {e}")

    if migrated_count > 0:
        logger.info(f"Successfully migrated {migrated_count} legacy sessions from {json_path} into relational database.")
    return migrated_count
