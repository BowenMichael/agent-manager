"""
Cloud-side Workstation Hub for Hybrid Remote Execution.
Tracks connected local developer workstations and routes dispatched tasks.
Adheres strictly to Anti-Monolith guidelines (< 250 lines, < 40 lines per function).
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable, Set
from fastapi import WebSocket

from agent_manager.bridge.models import (
    WorkstationInfo,
    WorkstationTaskRequest,
    WorkstationStreamChunk,
    WorkstationTaskResult,
)

logger = logging.getLogger("agent_manager.bridge.hub")


class WorkstationHub:
    """Central registry & routing hub for connected developer workstations."""

    def __init__(self):
        self._workstations: Dict[str, WorkstationInfo] = {}
        self._sockets: Dict[str, WebSocket] = {}
        self._task_listeners: Dict[str, List[Callable[[WorkstationStreamChunk], Any]]] = {}
        self._lock = asyncio.Lock()

    async def register_workstation(
        self,
        workstation_id: str,
        socket: WebSocket,
        info: Optional[WorkstationInfo] = None
    ) -> WorkstationInfo:
        """Registers a new workstation WebSocket connection."""
        async with self._lock:
            if info is None:
                info = WorkstationInfo(id=workstation_id)
            info.last_heartbeat_at = time.time()
            info.status = "idle"
            self._workstations[workstation_id] = info
            self._sockets[workstation_id] = socket
            logger.info(f"Registered workstation: {workstation_id} ({info.name})")
            return info

    async def unregister_workstation(self, workstation_id: str):
        """Unregisters a disconnected workstation."""
        async with self._lock:
            self._workstations.pop(workstation_id, None)
            self._sockets.pop(workstation_id, None)
            logger.info(f"Unregistered workstation: {workstation_id}")

    def get_workstation(self, workstation_id: str) -> Optional[WorkstationInfo]:
        """Retrieves info for a connected workstation."""
        return self._workstations.get(workstation_id)

    def list_workstations(self) -> List[WorkstationInfo]:
        """Lists all currently connected workstations."""
        return list(self._workstations.values())

    def update_heartbeat(self, workstation_id: str):
        """Updates last seen timestamp for a workstation."""
        if workstation_id in self._workstations:
            self._workstations[workstation_id].last_heartbeat_at = time.time()

    async def dispatch_task(
        self,
        task: WorkstationTaskRequest,
        target_workstation_id: Optional[str] = None
    ) -> bool:
        """Dispatches a task payload to a specified or next available workstation."""
        socket, ws_id = self._select_workstation(target_workstation_id)
        if not socket or not ws_id:
            logger.warning(f"No available workstation to dispatch task {task.task_id}")
            return False

        payload = {
            "type": "dispatch_task",
            "task": task.model_dump()
        }
        try:
            await socket.send_json(payload)
            if ws_id in self._workstations:
                self._workstations[ws_id].status = "busy"
                if task.task_id not in self._workstations[ws_id].active_tasks:
                    self._workstations[ws_id].active_tasks.append(task.task_id)
            logger.info(f"Dispatched task {task.task_id} to workstation {ws_id}")
            return True
        except Exception as e:
            logger.error(f"Failed sending dispatch to workstation {ws_id}: {e}")
            return False

    def _select_workstation(self, target_id: Optional[str]) -> tuple[Optional[WebSocket], Optional[str]]:
        """Selects target socket and ID based on preference or availability."""
        if target_id and target_id in self._sockets:
            return self._sockets[target_id], target_id
        for ws_id, sock in self._sockets.items():
            return sock, ws_id
        return None, None

    def subscribe_task_stream(
        self,
        task_id: str,
        callback: Callable[[WorkstationStreamChunk], Any]
    ):
        """Subscribes a listener callback to streaming events for a specific task."""
        if task_id not in self._task_listeners:
            self._task_listeners[task_id] = []
        self._task_listeners[task_id].append(callback)

    def unsubscribe_task_stream(self, task_id: str, callback: Optional[Callable] = None):
        """Removes a stream subscriber or all subscribers for a task."""
        if task_id in self._task_listeners:
            if callback:
                self._task_listeners[task_id] = [cb for cb in self._task_listeners[task_id] if cb != callback]
            else:
                self._task_listeners.pop(task_id, None)

    async def broadcast_stream_chunk(self, chunk: WorkstationStreamChunk):
        """Dispatches an incoming stream chunk to all registered task listeners."""
        listeners = self._task_listeners.get(chunk.task_id, [])
        for listener in list(listeners):
            try:
                res = listener(chunk)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error(f"Error invoking stream listener for task {chunk.task_id}: {e}")

        # Update workstation status if task is completed
        if chunk.chunk_type in ("complete", "error"):
            self._handle_task_completion(chunk.workstation_id, chunk.task_id)

    def _handle_task_completion(self, workstation_id: str, task_id: str):
        """Marks task finished on workstation record."""
        ws_info = self._workstations.get(workstation_id)
        if ws_info and task_id in ws_info.active_tasks:
            ws_info.active_tasks.remove(task_id)
            if not ws_info.active_tasks:
                ws_info.status = "idle"


# Global singleton workstation hub
workstation_hub = WorkstationHub()
