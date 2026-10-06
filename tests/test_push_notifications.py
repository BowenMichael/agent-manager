"""
Unit and Integration Tests for Push Notifications.
Tests device registry, message payload formatting, session milestone triggers, and REST endpoints.
Adheres strictly to Anti-Monolith guidelines (< 250 lines, < 40 lines per function).
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from agent_manager.server import app
from agent_manager.services.push_notification_service import (
    PushNotificationService,
    DeviceRegistration,
    PushMessagePayload,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def service():
    return PushNotificationService()


def test_device_registration_lifecycle(service):
    """Verifies registering, listing, and unregistering devices."""
    reg = DeviceRegistration(
        push_token="ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
        device_name="iPhone 15 Pro",
        platform="ios"
    )
    saved = service.register_device(reg)
    assert saved.push_token == reg.push_token
    assert len(service.list_devices()) == 1

    removed = service.unregister_device(reg.push_token)
    assert removed is True
    assert len(service.list_devices()) == 0


def test_notification_text_formatting(service):
    """Verifies human-friendly text for session milestones."""
    t_rev, b_rev = service._build_notification_text("in_review", "sess-123", 24, None)
    assert "Ready for Review" in t_rev
    assert "Issue #24" in t_rev

    t_pau, b_pau = service._build_notification_text("paused", "sess-123", 24, "Turn limit exceeded")
    assert "Guardrail Alert" in t_pau
    assert "Turn limit exceeded" in b_pau

    t_err, b_err = service._build_notification_text("failed", "sess-123", None, "Git clone error")
    assert "Execution Failed" in t_err
    assert "Git clone error" in b_err

    t_done, b_done = service._build_notification_text("done", "sess-123", 42, None)
    assert "Completed & Merged" in t_done


def test_send_push_notification_mock(service):
    """Verifies sending push notifications via mocked HTTP client."""
    reg = DeviceRegistration(push_token="ExponentPushToken[test]", device_name="Test Phone")
    service.register_device(reg)

    async def _test():
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"data": [{"status": "ok"}]}
            mock_post.return_value = mock_resp

            res = await service.notify_session_transition("sess-99", "in_review", 24)
            assert res["status"] == "success"
            mock_post.assert_called_once()

    asyncio.run(_test())


def test_notifications_api_endpoints(client):
    """Tests REST endpoints for device registration and listing."""
    res_reg = client.post("/api/notifications/register", json={
        "push_token": "ExponentPushToken[api-test-token]",
        "device_name": "Pixel 8",
        "platform": "android"
    })
    assert res_reg.status_code == 200
    assert res_reg.json()["push_token"] == "ExponentPushToken[api-test-token]"

    res_list = client.get("/api/notifications/devices")
    assert res_list.status_code == 200
    tokens = [d["push_token"] for d in res_list.json()]
    assert "ExponentPushToken[api-test-token]" in tokens

    res_del = client.delete("/api/notifications/devices/ExponentPushToken[api-test-token]")
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True
