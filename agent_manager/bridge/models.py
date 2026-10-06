"""
Models for Workstation Bridge & Hybrid Remote Execution.
Defines data structures for workstation registration, task dispatch, and streaming events.
Adheres strictly to Anti-Monolith guidelines (< 250 lines).
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
import time


class WorkstationInfo(BaseModel):
    """Metadata describing a connected local developer workstation."""
    id: str
    name: str = "Local Workstation"
    hostname: str = "localhost"
    platform: str = "windows"
    capabilities: List[str] = Field(default_factory=lambda: ["agy_cli", "git_worktrees"])
    status: str = "connected"
    connected_at: float = Field(default_factory=time.time)
    last_heartbeat_at: float = Field(default_factory=time.time)
    active_tasks: List[str] = Field(default_factory=list)


class WorkstationTaskRequest(BaseModel):
    """Payload dispatched to a workstation to execute a task in a worktree."""
    task_id: str
    issue_number: int
    repo: str
    branch_name: str
    task_description: str
    worktree_path: Optional[str] = None
    auth_token: Optional[str] = None
    environment: Dict[str, str] = Field(default_factory=dict)
    command_override: Optional[str] = None


class WorkstationStreamChunk(BaseModel):
    """Streaming chunk emitted by a workstation during local task execution."""
    task_id: str
    workstation_id: str
    chunk_type: str = "stdout"  # stdout, stderr, thought, tool_call, diff, status, complete, error
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class WorkstationTaskResult(BaseModel):
    """Final summary outcome of a task executed on a workstation."""
    task_id: str
    workstation_id: str
    success: bool
    exit_code: int = 0
    error_message: Optional[str] = None
    execution_time_seconds: float = 0.0
