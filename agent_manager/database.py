"""
Database Facade Module for Agent Swarm Relational Storage.
Provides centralized database initialization, session management, and metrics compliance.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

from typing import Dict, Optional
from sqlalchemy.orm import Session
from agent_manager.models import AgentSessionInfo
from agent_manager.db.connection import (
    get_engine, get_session_factory, get_db_session, resolve_database_url
)
from agent_manager.db.models import Base, AgentSessionRecord, ConversationMessageRecord
from agent_manager.db.repository import (
    init_schema, save_session, load_all_sessions, get_session, delete_session
)
from agent_manager.db.migrate_json import migrate_json_to_database


def init_db(engine=None):
    """Initializes schema and runs automatic migration from legacy JSON if needed."""
    target_engine = engine or get_engine()
    init_schema(target_engine)
    migrate_json_to_database()


def get_db():
    """FastAPI dependency yielding a transactional database session."""
    with get_db_session() as session:
        yield session


def save_session_record(session: AgentSessionInfo, db: Optional[Session] = None):
    """Facade for persisting or updating a session record."""
    save_session(session, external_db=db)


def load_session_records(db: Optional[Session] = None) -> Dict[str, AgentSessionInfo]:
    """Facade for loading all session records."""
    return load_all_sessions(external_db=db)
