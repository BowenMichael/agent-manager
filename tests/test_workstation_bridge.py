"""
Unit and Integration Tests for Workstation Bridge & Hybrid Runner Architecture.
Tests models, hub routing, local worktree executor, and FastAPI REST/WebSocket endpoints.
Adheres strictly to Anti-Monolith guidelines (< 250 lines, < 40 lines per function).
"""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from agent_manager.server import app
from agent_manager.bridge.models import (
    WorkstationInfo,
    WorkstationTaskRequest,
    WorkstationStreamChunk,
    WorkstationTaskResult,
)
from agent_manager.bridge.hub import WorkstationHub
from agent_manager.bridge.executor import LocalWorktreeExecutor


@pytest.fixture
def client():
    return TestClient(app)


def test_workstation_models():
    """Verifies bridge models serializations and defaults."""
    info = WorkstationInfo(id="ws-dev-1", name="Dev Laptop", platform="windows")
    assert info.id == "ws-dev-1"
    assert info.platform == "windows"
    assert "agy_cli" in info.capabilities

    req = WorkstationTaskRequest(
        task_id="task-123",
        issue_number=27,
        repo="BowenMichael/agent-manager",
        branch_name="feat/issue-27-test",
        task_description="Test bridge execution"
    )
    assert req.issue_number == 27
    assert req.task_id == "task-123"

    chunk = WorkstationStreamChunk(
        task_id="task-123",
        workstation_id="ws-dev-1",
        chunk_type="stdout",
        payload={"text": "Step 1 complete"}
    )
    assert chunk.payload["text"] == "Step 1 complete"


def test_hub_lifecycle_and_dispatch():
    """Verifies workstation registration, heartbeat, and task dispatch."""
    async def _run_test():
        hub = WorkstationHub()
        mock_ws = AsyncMock()
        info = WorkstationInfo(id="ws-1", name="Workstation 1")
        
        await hub.register_workstation("ws-1", mock_ws, info)
        assert hub.get_workstation("ws-1") is not None
        assert len(hub.list_workstations()) == 1

        hub.update_heartbeat("ws-1")

        task = WorkstationTaskRequest(
            task_id="t-1",
            issue_number=10,
            repo="test/repo",
            branch_name="feat/t1",
            task_description="Build feature"
        )
        dispatched = await hub.dispatch_task(task, "ws-1")
        assert dispatched is True
        mock_ws.send_json.assert_awaited_once()

        await hub.unregister_workstation("ws-1")
        assert len(hub.list_workstations()) == 0

    asyncio.run(_run_test())


def test_hub_stream_listeners():
    """Verifies subscribing and broadcasting stream chunks."""
    async def _run_test():
        hub = WorkstationHub()
        received = []

        def on_chunk(c: WorkstationStreamChunk):
            received.append(c)

        hub.subscribe_task_stream("task-99", on_chunk)
        
        chunk = WorkstationStreamChunk(
            task_id="task-99",
            workstation_id="ws-1",
            chunk_type="stdout",
            payload={"line": "Building code"}
        )
        await hub.broadcast_stream_chunk(chunk)
        assert len(received) == 1
        assert received[0].task_id == "task-99"

        hub.unsubscribe_task_stream("task-99", on_chunk)
        await hub.broadcast_stream_chunk(chunk)
        assert len(received) == 1

    asyncio.run(_run_test())


def test_local_executor_preparation():
    """Verifies worktree path calculation and command generation."""
    executor = LocalWorktreeExecutor(workspace_root=Path("/fake/root"))
    task = WorkstationTaskRequest(
        task_id="t-2",
        issue_number=42,
        repo="BowenMichael/agent-manager",
        branch_name="feat/42",
        task_description="Fix bug"
    )
    worktree_path = executor.prepare_worktree_path(task)
    assert "issue-42" in str(worktree_path)

    cmd = executor.build_command(task, worktree_path)
    assert "--issue" in cmd
    assert "42" in cmd


def test_workstation_api_endpoints(client):
    """Tests REST endpoints for workstation listing and details."""
    res = client.get("/api/workstations")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    res_404 = client.get("/api/workstations/non-existent-ws")
    assert res_404.status_code == 404
