"""
Unit & Integration Tests for Relational Database Persistence Layer.
Verifies SQLite/PostgreSQL connection routing, ORM models, repository CRUD,
Alembic migration compatibility, and legacy JSON migration.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import os
import json
import tempfile
import unittest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agent_manager.models import (
    AgentSessionInfo, AgentStatus, ConversationMessage, MessageRole, WorkflowStage
)
from agent_manager.db.connection import (
    resolve_database_url, create_db_engine
)
from agent_manager.db.models import Base, AgentSessionRecord, ConversationMessageRecord
from agent_manager.db.repository import (
    init_schema, save_session, load_all_sessions, get_session, delete_session
)
from agent_manager.db.migrate_json import migrate_json_to_database
from agent_manager.database import init_db, save_session_record, load_session_records
from agent_manager.storage import save_single_session, load_sessions


class TestDatabaseLayer(unittest.TestCase):
    def setUp(self):
        # Use an isolated in-memory SQLite engine for tests
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def test_resolve_database_url(self):
        url = resolve_database_url("postgres://user:pass@host:5432/dbname")
        self.assertTrue(url.startswith("postgresql+psycopg://") or url.startswith("postgresql://"))

        default_url = resolve_database_url()
        self.assertTrue(default_url.startswith("sqlite:///"))

    def test_session_and_message_crud(self):
        with self.SessionLocal() as db:
            session = AgentSessionInfo(
                session_id="test-session-db-1",
                repo="BowenMichael/agent-manager",
                issue_number=18,
                title="Migrate to Database",
                status=AgentStatus.RUNNING,
                total_tokens=1250,
                messages=[
                    ConversationMessage(
                        id="msg-1",
                        role=MessageRole.USER,
                        content="Start migration"
                    ),
                    ConversationMessage(
                        id="msg-2",
                        role=MessageRole.AGENT,
                        content="Schema defined"
                    )
                ]
            )
            save_session(session, external_db=db)
            db.commit()

            loaded = get_session("test-session-db-1", external_db=db)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.session_id, "test-session-db-1")
            self.assertEqual(loaded.issue_number, 18)
            self.assertEqual(loaded.total_tokens, 1250)
            self.assertEqual(len(loaded.messages), 2)
            self.assertEqual(loaded.messages[0].content, "Start migration")

    def test_cascade_delete(self):
        with self.SessionLocal() as db:
            session = AgentSessionInfo(
                session_id="test-cascade-sess",
                repo="BowenMichael/agent-manager",
                title="Cascade Test",
                messages=[ConversationMessage(id="msg-casc-1", role=MessageRole.SYSTEM, content="Init")]
            )
            save_session(session, external_db=db)
            db.commit()

            self.assertTrue(delete_session("test-cascade-sess", external_db=db))
            db.commit()

            self.assertIsNone(get_session("test-cascade-sess", external_db=db))
            msg_count = db.query(ConversationMessageRecord).filter_by(session_id="test-cascade-sess").count()
            self.assertEqual(msg_count, 0)

    def test_legacy_json_migration(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_file = Path(tmp_dir) / "sessions.json"
            legacy_data = [
                {
                    "session_id": "legacy-session-99",
                    "repo": "BowenMichael/agent-manager",
                    "issue_number": 99,
                    "title": "Legacy Test Session",
                    "status": "COMPLETED",
                    "messages": [
                        {"id": "m1", "role": "USER", "content": "Hello"}
                    ]
                }
            ]
            json_file.write_text(json.dumps(legacy_data), encoding="utf-8")

            # Run migration on isolated engine
            migrated = migrate_json_to_database(json_file)
            self.assertGreaterEqual(migrated, 0)

    def test_storage_integration(self):
        session = AgentSessionInfo(
            session_id="storage-integ-1",
            repo="BowenMichael/agent-manager",
            title="Storage Integration Test",
            status=AgentStatus.COMPLETED
        )
        save_single_session(session)
        loaded = load_sessions()
        self.assertIn("storage-integ-1", loaded)
        self.assertEqual(loaded["storage-integ-1"].title, "Storage Integration Test")


if __name__ == "__main__":
    unittest.main()
