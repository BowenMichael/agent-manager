"""
FastAPI Routes for Push Notifications.
Provides endpoints for mobile device registration and test dispatching.
Adheres strictly to Anti-Monolith guidelines (< 250 lines, < 40 lines per function).
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from agent_manager.services.push_notification_service import (
    push_service,
    DeviceRegistration,
    PushMessagePayload,
)

router = APIRouter(tags=["notifications"])


class TestPushRequest(BaseModel):
    title: str = "Test Notification"
    body: str = "This is a test push notification from Agent Manager."
    token_override: Optional[str] = None


@router.post("/api/notifications/register", response_model=DeviceRegistration)
def register_device_token(registration: DeviceRegistration):
    """Registers or updates a mobile device push token for milestone alerts."""
    if not registration.push_token.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="push_token cannot be empty"
        )
    return push_service.register_device(registration)


@router.get("/api/notifications/devices", response_model=List[DeviceRegistration])
def list_registered_devices():
    """Lists all mobile devices registered to receive push notifications."""
    return push_service.list_devices()


@router.delete("/api/notifications/devices/{push_token}")
def unregister_device_token(push_token: str):
    """Unregisters a mobile device token."""
    removed = push_service.unregister_device(push_token)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device token not found"
        )
    return {"success": True, "message": "Device token unregistered."}


@router.post("/api/notifications/test")
async def send_test_notification(req: TestPushRequest):
    """Dispatches a test push notification to registered devices."""
    recipients = [req.token_override] if req.token_override else [d.push_token for d in push_service.list_devices()]
    if not recipients:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No registered devices or token override provided"
        )
    payload = PushMessagePayload(
        to=recipients,
        title=req.title,
        body=req.body,
        data={"test": True}
    )
    result = await push_service.send_push(payload)
    return {"success": True, "result": result}
