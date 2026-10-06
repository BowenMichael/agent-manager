"""
Data Mappers between SQLAlchemy Relational Models and Pydantic Models.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import json
from typing import List
from agent_manager.models import (
    AgentSessionInfo, AgentStatus, ConversationMessage, MessageRole, WorkflowStage
)
from agent_manager.db.models import AgentSessionRecord, ConversationMessageRecord


def to_pydantic_message(rec: ConversationMessageRecord) -> ConversationMessage:
    """Converts a database message record into a Pydantic ConversationMessage."""
    args = None
    if rec.tool_args_json:
        try:
            args = json.loads(rec.tool_args_json)
        except Exception:
            args = None

    return ConversationMessage(
        id=rec.id,
        role=MessageRole(rec.role) if rec.role in MessageRole.__members__.values() else MessageRole.SYSTEM,
        content=rec.content or "",
        timestamp=rec.timestamp,
        tool_name=rec.tool_name,
        tool_args=args,
        tool_output=rec.tool_output
    )


def to_pydantic_session(rec: AgentSessionRecord) -> AgentSessionInfo:
    """Converts an AgentSessionRecord database row to a Pydantic AgentSessionInfo."""
    messages = [to_pydantic_message(m) for m in (rec.messages or [])]
    seen_ids = []
    if rec.seen_comment_ids_json:
        try:
            seen_ids = json.loads(rec.seen_comment_ids_json)
        except Exception:
            seen_ids = []

    return AgentSessionInfo(
        session_id=rec.session_id,
        repo=rec.repo or "",
        issue_number=rec.issue_number,
        pr_url=rec.pr_url,
        pr_number=rec.pr_number,
        title=rec.title,
        status=AgentStatus(rec.status) if rec.status in AgentStatus.__members__.values() else AgentStatus.INITIALIZING,
        worktree_path=rec.worktree_path,
        git_branch=rec.git_branch,
        started_at=rec.started_at,
        updated_at=rec.updated_at,
        turn_count=rec.turn_count,
        max_turns=rec.max_turns,
        consecutive_duplicate_tool_count=rec.consecutive_duplicate_tool_count,
        consecutive_view_file_count=rec.consecutive_view_file_count,
        last_tool_signature=rec.last_tool_signature,
        circuit_breaker_triggered=rec.circuit_breaker_triggered,
        token_count=rec.token_count,
        input_tokens=rec.input_tokens,
        output_tokens=rec.output_tokens,
        thinking_tokens=rec.thinking_tokens,
        cache_read_tokens=rec.cache_read_tokens,
        total_tokens=rec.total_tokens,
        duration_seconds=rec.duration_seconds,
        max_tokens=rec.max_tokens,
        quota_percent=rec.quota_percent,
        messages=messages,
        error_message=rec.error_message,
        agy_mode=rec.agy_mode or "terminal",
        terminal_command=rec.terminal_command,
        model=rec.model,
        effort=rec.effort,
        current_activity=rec.current_activity or "IDLE",
        last_activity_at=rec.last_activity_at,
        is_stalled=rec.is_stalled,
        quota_exceeded=rec.quota_exceeded,
        quota_message=rec.quota_message,
        seen_comment_ids=seen_ids,
        last_issue_body=rec.last_issue_body,
        is_archived=rec.is_archived,
        archived_at=rec.archived_at,
        is_compacted=rec.is_compacted,
        compact_summary=rec.compact_summary,
        workflow_pipeline_enabled=rec.workflow_pipeline_enabled,
        workflow_stage=WorkflowStage(rec.workflow_stage) if rec.workflow_stage in WorkflowStage.__members__.values() else WorkflowStage.DIRECT,
        pipeline_summary=rec.pipeline_summary,
        pipeline_plan=rec.pipeline_plan,
        pid=rec.pid,
        stream_log_file=rec.stream_log_file,
        exit_code_file=rec.exit_code_file,
        stream_log_offset=rec.stream_log_offset
    )


def apply_pydantic_to_record(rec: AgentSessionRecord, info: AgentSessionInfo):
    """Maps fields from Pydantic AgentSessionInfo into SQLAlchemy record."""
    rec.repo = info.repo
    rec.issue_number = info.issue_number
    rec.pr_url = info.pr_url
    rec.pr_number = info.pr_number
    rec.title = info.title
    rec.status = info.status.value if hasattr(info.status, "value") else str(info.status)
    rec.worktree_path = info.worktree_path
    rec.git_branch = info.git_branch
    rec.started_at = info.started_at
    rec.updated_at = info.updated_at
    rec.turn_count = info.turn_count
    rec.max_turns = info.max_turns
    rec.consecutive_duplicate_tool_count = info.consecutive_duplicate_tool_count
    rec.consecutive_view_file_count = info.consecutive_view_file_count
    rec.last_tool_signature = info.last_tool_signature
    rec.circuit_breaker_triggered = info.circuit_breaker_triggered
    rec.token_count = info.token_count
    rec.input_tokens = info.input_tokens
    rec.output_tokens = info.output_tokens
    rec.thinking_tokens = info.thinking_tokens
    rec.cache_read_tokens = info.cache_read_tokens
    rec.total_tokens = info.total_tokens
    rec.duration_seconds = info.duration_seconds
    rec.max_tokens = info.max_tokens
    rec.quota_percent = info.quota_percent
    rec.error_message = info.error_message
    rec.agy_mode = info.agy_mode
    rec.terminal_command = info.terminal_command
    rec.model = info.model
    rec.effort = info.effort
    rec.current_activity = info.current_activity
    rec.last_activity_at = info.last_activity_at
    rec.is_stalled = info.is_stalled
    rec.quota_exceeded = info.quota_exceeded
    rec.quota_message = info.quota_message
    rec.seen_comment_ids_json = json.dumps(info.seen_comment_ids or [])
    rec.last_issue_body = info.last_issue_body
    rec.is_archived = info.is_archived
    rec.archived_at = info.archived_at
    rec.is_compacted = info.is_compacted
    rec.compact_summary = info.compact_summary
    rec.workflow_pipeline_enabled = info.workflow_pipeline_enabled
    rec.workflow_stage = info.workflow_stage.value if hasattr(info.workflow_stage, "value") else str(info.workflow_stage)
    rec.pipeline_summary = info.pipeline_summary
    rec.pipeline_plan = info.pipeline_plan
    rec.pid = info.pid
    rec.stream_log_file = info.stream_log_file
    rec.exit_code_file = info.exit_code_file
    rec.stream_log_offset = info.stream_log_offset


def create_message_records(messages: List[ConversationMessage], session_id: str) -> List[ConversationMessageRecord]:
    """Builds a list of ConversationMessageRecord instances from Pydantic messages."""
    records = []
    for idx, msg in enumerate(messages):
        args_json = json.dumps(msg.tool_args) if msg.tool_args else None
        role_val = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
        records.append(
            ConversationMessageRecord(
                id=msg.id,
                session_id=session_id,
                order_idx=idx,
                role=role_val,
                content=msg.content or "",
                timestamp=msg.timestamp,
                tool_name=msg.tool_name,
                tool_args_json=args_json,
                tool_output=msg.tool_output
            )
        )
    return records
