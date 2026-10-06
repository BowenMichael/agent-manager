"""
Workstation Bridge Module.
Provides hybrid local/cloud runner architecture for remote autonomous execution.
"""

from agent_manager.bridge.models import (
    WorkstationInfo,
    WorkstationTaskRequest,
    WorkstationStreamChunk,
    WorkstationTaskResult,
)
from agent_manager.bridge.hub import WorkstationHub, workstation_hub
from agent_manager.bridge.executor import LocalWorktreeExecutor
from agent_manager.bridge.client import WorkstationDaemon

__all__ = [
    "WorkstationInfo",
    "WorkstationTaskRequest",
    "WorkstationStreamChunk",
    "WorkstationTaskResult",
    "WorkstationHub",
    "workstation_hub",
    "LocalWorktreeExecutor",
    "WorkstationDaemon",
]
