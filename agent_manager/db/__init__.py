"""
Relational Database Package for Agent Swarm.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

from agent_manager.db.connection import (
    get_engine, get_session_factory, get_db_session, create_db_engine, resolve_database_url
)
from agent_manager.db.models import Base, AgentSessionRecord, ConversationMessageRecord
from agent_manager.db.repository import (
    init_schema, save_session, load_all_sessions, get_session, delete_session
)
from agent_manager.db.migrate_json import migrate_json_to_database

__all__ = [
    "get_engine",
    "get_session_factory",
    "get_db_session",
    "create_db_engine",
    "resolve_database_url",
    "Base",
    "AgentSessionRecord",
    "ConversationMessageRecord",
    "init_schema",
    "save_session",
    "load_all_sessions",
    "get_session",
    "delete_session",
    "migrate_json_to_database",
]
