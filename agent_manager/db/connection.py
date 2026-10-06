"""
Relational Database Connection & Engine Configuration.
Supports PostgreSQL (Render/Production) and SQLite (Local Development/Testing).
Adheres to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import os
from pathlib import Path
from typing import Optional, Generator
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def resolve_database_url(custom_url: Optional[str] = None) -> str:
    """Resolves target database connection string with production/dev fallback."""
    if custom_url:
        url = custom_url
    else:
        url = os.getenv("DATABASE_URL", "").strip()

    if not url:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        db_path = DATA_DIR / "agent_manager.db"
        return f"sqlite:///{db_path.as_posix()}"

    # Normalize Render / Heroku postgres schemas to postgresql+psycopg://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def configure_sqlite_pragmas(dbapi_connection, connection_record):
    """Configures high-concurrency WAL mode and pragmas for SQLite engines."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=10000;")
    except Exception:
        pass
    finally:
        cursor.close()


def create_db_engine(url: Optional[str] = None) -> Engine:
    """Builds and returns a configured SQLAlchemy engine."""
    db_url = resolve_database_url(url)
    is_sqlite = db_url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}

    engine = create_engine(
        db_url,
        echo=False,
        future=True,
        connect_args=connect_args,
        pool_pre_ping=True
    )
    if is_sqlite:
        event.listen(engine, "connect", configure_sqlite_pragmas)
    return engine


_GLOBAL_ENGINE: Optional[Engine] = None
_SESSION_FACTORY: Optional[sessionmaker] = None


def get_engine() -> Engine:
    """Retrieves or lazily initializes the singleton SQLAlchemy Engine."""
    global _GLOBAL_ENGINE
    if _GLOBAL_ENGINE is None:
        _GLOBAL_ENGINE = create_db_engine()
    return _GLOBAL_ENGINE


def get_session_factory() -> sessionmaker:
    """Retrieves or initializes the session factory bound to the global engine."""
    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        _SESSION_FACTORY = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
    return _SESSION_FACTORY


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for safe transactional database sessions."""
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
