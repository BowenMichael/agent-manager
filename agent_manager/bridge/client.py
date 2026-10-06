"""
Workstation Bridge Daemon.
Runs locally on developer machine, establishes outbound WebSocket connection to cloud control plane.
Requires zero open inbound ports. Dispatches local execution and streams events upstream.
Adheres strictly to Anti-Monolith guidelines (< 250 lines, < 40 lines per function).
"""

import asyncio
import json
import logging
import platform
import socket
import time
from pathlib import Path
from typing import Optional, Dict, Any

from agent_manager.bridge.models import (
    WorkstationInfo,
    WorkstationTaskRequest,
    WorkstationStreamChunk,
)
from agent_manager.bridge.executor import LocalWorktreeExecutor

logger = logging.getLogger("agent_manager.bridge.client")


class WorkstationDaemon:
    """Outbound daemon connecting local workstation to cloud Agent Manager."""

    def __init__(
        self,
        server_ws_url: str,
        workstation_id: Optional[str] = None,
        name: Optional[str] = None,
        auth_token: Optional[str] = None,
        workspace_root: Optional[Path] = None
    ):
        self.server_ws_url = server_ws_url
        self.workstation_id = workstation_id or f"ws-{socket.gethostname().lower()}"
        self.name = name or f"{socket.gethostname()} Developer Workstation"
        self.auth_token = auth_token
        self.executor = LocalWorktreeExecutor(workspace_root=workspace_root)
        self._running = False
        self._ws = None

    def get_workstation_info(self) -> WorkstationInfo:
        """Constructs current workstation info payload."""
        return WorkstationInfo(
            id=self.workstation_id,
            name=self.name,
            hostname=socket.gethostname(),
            platform=platform.system().lower(),
            capabilities=["agy_cli", "git_worktrees", "python_runner"],
            status="idle"
        )

    async def handle_server_message(self, message_text: str):
        """Processes an incoming command from cloud server."""
        try:
            data = json.loads(message_text)
            msg_type = data.get("type")
            if msg_type == "dispatch_task":
                task_data = data.get("task", {})
                task_req = WorkstationTaskRequest(**task_data)
                asyncio.create_task(self._run_and_stream_task(task_req))
            elif msg_type == "ping":
                await self._send_json({"type": "pong", "timestamp": time.time()})
        except Exception as exc:
            logger.error(f"Error handling server message: {exc}")

    async def _run_and_stream_task(self, task: WorkstationTaskRequest):
        """Executes task locally and sends stream chunks upstream."""
        logger.info(f"Starting local execution for task: {task.task_id} (Issue #{task.issue_number})")
        async for chunk in self.executor.execute_task_stream(task, self.workstation_id):
            await self._send_json({
                "type": "stream_chunk",
                "chunk": chunk.model_dump()
            })
        logger.info(f"Completed local execution for task: {task.task_id}")

    async def _send_json(self, data: Dict[str, Any]):
        """Helper to send JSON payload over active WebSocket."""
        if self._ws:
            try:
                await self._ws.send(json.dumps(data))
            except Exception as e:
                logger.warning(f"Failed to send message to cloud: {e}")

    async def start(self):
        """Starts the daemon loop with auto-reconnect."""
        self._running = True
        logger.info(f"Workstation Bridge Daemon starting for {self.workstation_id} -> {self.server_ws_url}")
        
        while self._running:
            try:
                import websockets
                async with websockets.connect(self.server_ws_url) as ws:
                    self._ws = ws
                    logger.info("Connected outbound to Agent Manager Cloud Hub")
                    # Send registration
                    info = self.get_workstation_info()
                    await self._send_json({"type": "register", "info": info.model_dump()})
                    
                    heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                    try:
                        async for msg in ws:
                            await self.handle_server_message(msg)
                    finally:
                        heartbeat_task.cancel()
            except Exception as e:
                logger.warning(f"Bridge connection dropped: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    async def _heartbeat_loop(self):
        """Sends periodic heartbeat to maintain connection."""
        while self._running:
            await asyncio.sleep(15)
            await self._send_json({"type": "heartbeat", "workstation_id": self.workstation_id})

    def stop(self):
        """Stops the workstation daemon."""
        self._running = False
