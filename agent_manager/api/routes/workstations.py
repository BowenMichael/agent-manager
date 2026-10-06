"""
FastAPI Routes for Workstation Bridge & Hybrid Local Execution.
Provides REST and WebSocket endpoints for workstation registration and task dispatch.
Adheres strictly to Anti-Monolith guidelines (< 250 lines, < 40 lines per function).
"""

import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from pydantic import BaseModel

from agent_manager.bridge.models import (
    WorkstationInfo,
    WorkstationTaskRequest,
    WorkstationStreamChunk,
)
from agent_manager.bridge.hub import workstation_hub

logger = logging.getLogger("agent_manager.api.routes.workstations")
router = APIRouter(tags=["workstations"])


class DispatchResponse(BaseModel):
    success: bool
    task_id: str
    message: str


@router.get("/api/workstations", response_model=List[WorkstationInfo])
def list_connected_workstations():
    """Lists all currently active developer workstations connected via the bridge."""
    return workstation_hub.list_workstations()


@router.get("/api/workstations/{workstation_id}", response_model=WorkstationInfo)
def get_workstation_details(workstation_id: str):
    """Retrieves details of a specific connected developer workstation."""
    ws_info = workstation_hub.get_workstation(workstation_id)
    if not ws_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workstation '{workstation_id}' not found or disconnected."
        )
    return ws_info


@router.post("/api/workstations/dispatch", response_model=DispatchResponse)
async def dispatch_task_to_workstation(
    task: WorkstationTaskRequest,
    target_workstation_id: Optional[str] = None
):
    """Dispatches a task to a connected local developer workstation."""
    dispatched = await workstation_hub.dispatch_task(task, target_workstation_id)
    if not dispatched:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No available workstation connected to execute the requested task."
        )
    return DispatchResponse(
        success=True,
        task_id=task.task_id,
        message=f"Task {task.task_id} successfully dispatched to workstation."
    )


@router.websocket("/ws/workstations")
async def websocket_workstation_bridge(websocket: WebSocket):
    """Inbound WebSocket endpoint accepting outbound connections from workstation daemons."""
    await websocket.accept()
    current_ws_id: Optional[str] = None
    try:
        while True:
            raw_text = await websocket.receive_text()
            data = json.loads(raw_text)
            msg_type = data.get("type")

            if msg_type == "register":
                info_data = data.get("info", {})
                ws_info = WorkstationInfo(**info_data)
                current_ws_id = ws_info.id
                await workstation_hub.register_workstation(current_ws_id, websocket, ws_info)
                await websocket.send_json({"type": "registered", "workstation_id": current_ws_id})

            elif msg_type == "heartbeat":
                ws_id = data.get("workstation_id") or current_ws_id
                if ws_id:
                    workstation_hub.update_heartbeat(ws_id)
                    await websocket.send_json({"type": "heartbeat_ack", "timestamp": data.get("timestamp")})

            elif msg_type == "stream_chunk":
                chunk_data = data.get("chunk", {})
                chunk = WorkstationStreamChunk(**chunk_data)
                await workstation_hub.broadcast_stream_chunk(chunk)

    except WebSocketDisconnect:
        if current_ws_id:
            await workstation_hub.unregister_workstation(current_ws_id)
    except Exception as exc:
        logger.warning(f"Workstation WebSocket error: {exc}")
        if current_ws_id:
            await workstation_hub.unregister_workstation(current_ws_id)
