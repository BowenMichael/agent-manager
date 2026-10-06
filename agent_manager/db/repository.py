"""
Relational Database Repository for Agent Swarm Sessions.
Provides atomic CRUD operations and state persistence across restarts.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import logging
from typing import Dict, Optional, List
from sqlalchemy import select
from sqlalchemy.orm import Session
from agent_manager.models import AgentSessionInfo, AgentStatus, ConversationMessage, MessageRole
from agent_manager.db.connection import get_engine, get_db_session
from agent_manager.db.models import Base, AgentSessionRecord, ConversationMessageRecord
from agent_manager.db.mapper import (
    to_pydantic_session, apply_pydantic_to_record, create_message_records
)

logger = logging.getLogger("agent_manager.db.repository")


def init_schema(engine=None):
    """Creates database tables if they do not already exist."""
    target_engine = engine or get_engine()
    Base.metadata.create_all(bind=target_engine)
    logger.info("Relational database schema initialized successfully.")


def _persist_session_record(db: Session, session: AgentSessionInfo):
    """Internal helper to insert or update an AgentSessionRecord and its messages."""
    rec = db.get(AgentSessionRecord, session.session_id)
    if not rec:
        rec = AgentSessionRecord(session_id=session.session_id)
        apply_pydantic_to_record(rec, session)
        rec.messages = create_message_records(session.messages, session.session_id)
        db.add(rec)
    else:
        apply_pydantic_to_record(rec, session)
        db.query(ConversationMessageRecord).filter_by(session_id=session.session_id).delete()
        rec.messages = create_message_records(session.messages, session.session_id)


def save_session(session: AgentSessionInfo, external_db: Optional[Session] = None):
    """Atomically saves or updates a single session in the relational database."""
    if external_db:
        _persist_session_record(external_db, session)
        return

    with get_db_session() as db:
        _persist_session_record(db, session)


def _check_detached_worker_status(session: AgentSessionInfo):
    """Ensures detached worker status is correctly reconciled on load."""
    if session.status in [AgentStatus.RUNNING, AgentStatus.INITIALIZING]:
        from agent_manager.runners.process_manager import is_process_alive
        if session.pid and is_process_alive(session.pid):
            logger.info(f"Detached worker for session {session.session_id} is alive (PID: {session.pid}).")
        else:
            session.status = AgentStatus.IN_REVIEW
            session.messages.append(
                ConversationMessage(
                    id=f"restore-{len(session.messages)}",
                    role=MessageRole.SYSTEM,
                    content="🔄 [Task Cache Restored] Agent session reloaded from database. Chat remains active and ready for input or review."
                )
            )


def load_all_sessions(external_db: Optional[Session] = None) -> Dict[str, AgentSessionInfo]:
    """Loads all agent sessions from the relational database."""
    def _fetch(db: Session) -> Dict[str, AgentSessionInfo]:
        stmt = select(AgentSessionRecord).order_by(AgentSessionRecord.started_at.desc())
        records = db.scalars(stmt).all()
        sessions: Dict[str, AgentSessionInfo] = {}
        for rec in records:
            info = to_pydantic_session(rec)
            _check_detached_worker_status(info)
            sessions[info.session_id] = info
        return sessions

    if external_db:
        return _fetch(external_db)

    with get_db_session() as db:
        return _fetch(db)


def get_session(session_id: str, external_db: Optional[Session] = None) -> Optional[AgentSessionInfo]:
    """Retrieves a single session by session_id."""
    def _fetch_one(db: Session) -> Optional[AgentSessionInfo]:
        rec = db.get(AgentSessionRecord, session_id)
        if not rec:
            return None
        return to_pydantic_session(rec)

    if external_db:
        return _fetch_one(external_db)

    with get_db_session() as db:
        return _fetch_one(db)


def delete_session(session_id: str, external_db: Optional[Session] = None) -> bool:
    """Deletes a session and cascades deletes to its messages."""
    def _delete(db: Session) -> bool:
        rec = db.get(AgentSessionRecord, session_id)
        if not rec:
            return False
        db.delete(rec)
        return True

    if external_db:
        return _delete(external_db)

    with get_db_session() as db:
        return _delete(db)
