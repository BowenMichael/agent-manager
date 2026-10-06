"""
SQLAlchemy Relational Models for Agent Swarm Sessions and Messages.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

from typing import List, Optional
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class AgentSessionRecord(Base):
    """Relational table storing agent sessions with full state tracking."""
    __tablename__ = "agent_sessions"

    session_id = Column(String(128), primary_key=True, index=True)
    repo = Column(String(255), nullable=True, index=True)
    issue_number = Column(Integer, nullable=True, index=True)
    pr_url = Column(String(512), nullable=True)
    pr_number = Column(Integer, nullable=True)
    title = Column(String(512), nullable=False)
    status = Column(String(64), nullable=False, default="INITIALIZING", index=True)
    worktree_path = Column(String(1024), nullable=True)
    git_branch = Column(String(255), nullable=True)
    started_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)

    turn_count = Column(Integer, nullable=False, default=0)
    max_turns = Column(Integer, nullable=False, default=15)
    consecutive_duplicate_tool_count = Column(Integer, nullable=False, default=0)
    consecutive_view_file_count = Column(Integer, nullable=False, default=0)
    last_tool_signature = Column(String(255), nullable=True)
    circuit_breaker_triggered = Column(Boolean, nullable=False, default=False)

    token_count = Column(Integer, nullable=False, default=0)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    thinking_tokens = Column(Integer, nullable=False, default=0)
    cache_read_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    duration_seconds = Column(Float, nullable=False, default=0.0)
    max_tokens = Column(Integer, nullable=False, default=150000)
    quota_percent = Column(Float, nullable=False, default=0.0)

    error_message = Column(Text, nullable=True)
    agy_mode = Column(String(64), nullable=False, default="terminal")
    terminal_command = Column(Text, nullable=True)
    model = Column(String(128), nullable=True)
    effort = Column(String(64), nullable=True)
    current_activity = Column(String(128), nullable=True, default="IDLE")
    last_activity_at = Column(String(64), nullable=True)
    is_stalled = Column(Boolean, nullable=False, default=False)
    quota_exceeded = Column(Boolean, nullable=False, default=False)
    quota_message = Column(Text, nullable=True)
    seen_comment_ids_json = Column(Text, nullable=True, default="[]")
    last_issue_body = Column(Text, nullable=True)
    is_archived = Column(Boolean, nullable=False, default=False, index=True)
    archived_at = Column(String(64), nullable=True)
    is_compacted = Column(Boolean, nullable=False, default=False)
    compact_summary = Column(Text, nullable=True)

    workflow_pipeline_enabled = Column(Boolean, nullable=False, default=False)
    workflow_stage = Column(String(64), nullable=False, default="DIRECT")
    pipeline_summary = Column(Text, nullable=True)
    pipeline_plan = Column(Text, nullable=True)

    pid = Column(Integer, nullable=True)
    stream_log_file = Column(Text, nullable=True)
    exit_code_file = Column(Text, nullable=True)
    stream_log_offset = Column(Integer, nullable=False, default=0)

    messages = relationship(
        "ConversationMessageRecord",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ConversationMessageRecord.order_idx",
        lazy="selectin"
    )


class ConversationMessageRecord(Base):
    """Relational table storing individual conversation messages for sessions."""
    __tablename__ = "conversation_messages"

    id = Column(String(128), primary_key=True)
    session_id = Column(
        String(128),
        ForeignKey("agent_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    order_idx = Column(Integer, nullable=False, default=0)
    role = Column(String(64), nullable=False)
    content = Column(Text, nullable=False, default="")
    timestamp = Column(String(64), nullable=False)
    tool_name = Column(String(128), nullable=True)
    tool_args_json = Column(Text, nullable=True)
    tool_output = Column(Text, nullable=True)

    session = relationship("AgentSessionRecord", back_populates="messages")


Index("idx_messages_session_order", ConversationMessageRecord.session_id, ConversationMessageRecord.order_idx)
