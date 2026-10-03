from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class AgentStatus(str, Enum):
    IDLE = "IDLE"
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    IN_REVIEW = "IN_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class MessageRole(str, Enum):
    USER = "USER"
    AGENT = "AGENT"
    THOUGHT = "THOUGHT"
    TOOL_CALL = "TOOL_CALL"
    TOOL_RESULT = "TOOL_RESULT"
    SYSTEM = "SYSTEM"

class ConversationMessage(BaseModel):
    id: str
    role: MessageRole
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_output: Optional[str] = None

class AgentSessionInfo(BaseModel):
    session_id: str
    repo: str
    issue_number: Optional[int] = None
    title: str
    status: AgentStatus = AgentStatus.INITIALIZING
    worktree_path: Optional[str] = None
    git_branch: Optional[str] = None
    started_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    turn_count: int = 0
    token_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cache_read_tokens: int = 0
    total_tokens: int = 0
    duration_seconds: float = 0.0
    max_tokens: int = 150000
    quota_percent: float = 0.0
    messages: List[ConversationMessage] = []
    error_message: Optional[str] = None
    agy_mode: str = "terminal"
    terminal_command: Optional[str] = None
    model: Optional[str] = None
    effort: Optional[str] = None
    current_activity: Optional[str] = "IDLE"
    last_activity_at: Optional[str] = None
    is_stalled: bool = False
    quota_exceeded: bool = False
    quota_message: Optional[str] = None
    seen_comment_ids: List[str] = Field(default_factory=list)
    last_issue_body: Optional[str] = None
    is_compacted: bool = False
    compact_summary: Optional[str] = None

class SpawnRequest(BaseModel):
    repo: Optional[str] = None
    issue_number: Optional[int] = None
    title: Optional[str] = None
    prompt: str
    worktree_branch: Optional[str] = None
    model: Optional[str] = None
    effort: Optional[str] = None

class AddContextRequest(BaseModel):
    context: str

class StopAgentRequest(BaseModel):
    reason: Optional[str] = "Stopped by user via Agent Manager UI"

class SimulateWebhookRequest(BaseModel):
    event_type: str = "issues"
    action: str = "labeled"
    label: str = "agent:ready"
    issue_number: int = 6
    issue_title: str = "Milestone 1: Historical Calendar & Session Picker UI"
    issue_body: str = "Implement GETMeetings OpenF1 middleware integration, Season and Round dropdown selectors, and Grand Prix session card grid."
    repo: str = "BowenMichael/f1-frontend"

class SettingsUpdateRequest(BaseModel):
    default_model: Optional[str] = None
    effort_level: Optional[str] = None
    default_effort: Optional[str] = None
    allow_overage_credits: Optional[bool] = None
    max_session_tokens: Optional[int] = None
    gemini_api_key: Optional[str] = None
    agy_mode: Optional[str] = None
    compact_completed_chat: Optional[bool] = None
    default_repo: Optional[str] = None
