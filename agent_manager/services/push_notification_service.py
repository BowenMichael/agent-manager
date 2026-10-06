"""
Expo Push Notification Service.
Dispatches real-time push alerts to mobile devices for task milestones and guardrails.
Adheres strictly to Anti-Monolith guidelines (< 250 lines, < 40 lines per function).
"""

import logging
import time
import httpx
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("agent_manager.services.push_notification_service")

EXPO_PUSH_API_URL = "https://exp.host/--/api/v2/push/send"


class DeviceRegistration(BaseModel):
    """Registered mobile device token."""
    push_token: str
    device_name: str = "Mobile Device"
    platform: str = "ios"  # ios, android, web
    registered_at: float = Field(default_factory=time.time)
    last_seen_at: float = Field(default_factory=time.time)


class PushMessagePayload(BaseModel):
    """Expo push message structure."""
    to: List[str]
    title: str
    body: str
    data: Dict[str, Any] = Field(default_factory=dict)
    sound: str = "default"
    priority: str = "high"


class PushNotificationService:
    """Manages mobile device tokens and sends notifications via Expo API."""

    def __init__(self):
        self._devices: Dict[str, DeviceRegistration] = {}

    def register_device(self, reg: DeviceRegistration) -> DeviceRegistration:
        """Registers or updates a mobile device push token."""
        reg.last_seen_at = time.time()
        self._devices[reg.push_token] = reg
        logger.info(f"Registered device token: {reg.push_token[:15]}... ({reg.device_name})")
        return reg

    def unregister_device(self, push_token: str) -> bool:
        """Removes a registered device token."""
        return self._devices.pop(push_token, None) is not None

    def list_devices(self) -> List[DeviceRegistration]:
        """Returns all currently registered devices."""
        return list(self._devices.values())

    async def send_push(self, payload: PushMessagePayload) -> Dict[str, Any]:
        """Sends push notification batch to Expo Push API."""
        if not payload.to:
            return {"status": "skipped", "reason": "no_recipients"}

        messages = [
            {
                "to": token,
                "title": payload.title,
                "body": payload.body,
                "data": payload.data,
                "sound": payload.sound,
                "priority": payload.priority,
            }
            for token in payload.to
        ]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(EXPO_PUSH_API_URL, json=messages)
                return {
                    "status": "success" if res.status_code == 200 else "error",
                    "status_code": res.status_code,
                    "response": res.json() if res.status_code == 200 else res.text
                }
        except Exception as exc:
            logger.error(f"Failed sending push notification: {exc}")
            return {"status": "error", "error": str(exc)}

    async def notify_session_transition(
        self,
        session_id: str,
        status: str,
        issue_number: Optional[int] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Formats and sends push notification for agent lifecycle milestones."""
        tokens = list(self._devices.keys())
        if not tokens:
            return {"status": "skipped", "reason": "no_registered_devices"}

        title, body = self._build_notification_text(status, session_id, issue_number, reason)
        payload = PushMessagePayload(
            to=tokens,
            title=title,
            body=body,
            data={
                "session_id": session_id,
                "issue_number": issue_number,
                "status": status,
                "route": f"/(sessions)/{session_id}",
            }
        )
        return await self.send_push(payload)

    def _build_notification_text(
        self,
        status: str,
        session_id: str,
        issue_number: Optional[int],
        reason: Optional[str]
    ) -> tuple[str, str]:
        """Constructs human-friendly notification titles and message bodies."""
        issue_str = f"Issue #{issue_number}" if issue_number else f"Session {session_id[:8]}"
        if status == "in_review":
            return (f"🔍 {issue_str} Ready for Review", "Agent completed execution and is awaiting your verification.")
        elif status == "paused":
            r_str = f" Reason: {reason}" if reason else ""
            return (f"⚠️ {issue_str} Guardrail Alert", f"Agent paused due to token/complexity budget.{r_str}")
        elif status == "failed":
            r_str = f" Error: {reason}" if reason else ""
            return (f"❌ {issue_str} Execution Failed", f"Agent encountered an error.{r_str}")
        elif status == "done":
            return (f"✅ {issue_str} Completed & Merged", "Feature successfully merged and closed.")
        return (f"⚡ {issue_str} Status: {status}", f"Agent updated to {status}.")


# Global singleton push service
push_service = PushNotificationService()
