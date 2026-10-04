import asyncio
import json
import subprocess
from typing import Optional
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

import agent_manager.config as config
from agent_manager.config import STATIC_DIR
from pydantic import BaseModel
import os
from agent_manager.models import (
    SpawnRequest, AddContextRequest, StopAgentRequest,
    SimulateWebhookRequest, AgentSessionInfo, SettingsUpdateRequest
)
from agent_manager.runner import AgentRunnerManager
from agent_manager.storage import save_settings, load_settings
from agent_manager.webhooks import router as webhooks_router, process_github_event
from agent_manager.api.files import router as files_router
from agent_manager.api.context import router as context_router
from agent_manager.api.settings import router as settings_router
from agent_manager.poller import LocalGitWatcher


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("agent_manager.server")

from agent_manager.cron_dispatcher import dispatcher

watcher = LocalGitWatcher()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start local Git board watcher
    watcher.start()
    asyncio.create_task(runner.start_watchdog())
    # Startup: Start autonomous backlog cron dispatcher (runs every 10 mins)
    asyncio.create_task(dispatcher.start(initial_delay_seconds=600, interval_seconds=600))
    # Sync historical sessions into token telemetry cache
    try:
        from agent_manager.telemetry import sync_from_sessions_cache
        sync_from_sessions_cache(runner.sessions.values())
    except Exception as e:
        logger.warning(f"Failed to sync historical telemetry on startup: {e}")
    yield
    # Shutdown: Stop watcher and cron dispatcher
    watcher.stop()
    dispatcher.stop()

app = FastAPI(
    title="Agent Manager",
    description="Webhook Dispatcher & Live Control Plane for Google Antigravity Agents",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception processing {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Internal Server Error: {str(exc)}", "error": str(exc)},
    )

runner = AgentRunnerManager()
app.include_router(webhooks_router)
app.include_router(files_router)
app.include_router(context_router)
app.include_router(settings_router)

@app.get("/api/telemetry/tokens")
async def get_token_telemetry():
    """Returns aggregated token telemetry across multiple timescales (1h, 24h, 7d, 30d, all-time)."""
    from agent_manager.telemetry import get_timescale_metrics
    return get_timescale_metrics()

@app.get("/api/cron/status")
async def get_cron_status():
    return {
        "is_running": dispatcher.is_running,
        "last_run_at": dispatcher.last_run_at,
        "next_run_at": dispatcher.next_run_at,
        "history": dispatcher.dispatch_history[-10:]
    }

@app.post("/api/cron/dispatch-now")
async def trigger_cron_dispatch():
    return await dispatcher.check_and_dispatch()

@app.get("/api/agents", response_model=list[AgentSessionInfo])
async def list_agents(include_archived: bool = True):
    return runner.list_sessions(include_archived=include_archived)

@app.post("/api/agents/{session_id}/archive")
async def archive_agent(session_id: str):
    success = await runner.archive_agent(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return {"status": "ok", "message": f"Agent {session_id} archived"}

@app.post("/api/agents/{session_id}/unarchive")
async def unarchive_agent(session_id: str):
    success = await runner.unarchive_agent(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return {"status": "ok", "message": f"Agent {session_id} unarchived"}

@app.delete("/api/agents/{session_id}")
async def delete_agent(session_id: str):
    success = await runner.delete_agent(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return {"status": "ok", "message": f"Agent {session_id} deleted"}

@app.get("/api/agents/{session_id}", response_model=AgentSessionInfo)
async def get_agent(session_id: str):
    session = runner.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return session

@app.post("/api/agents/spawn", response_model=AgentSessionInfo)
async def spawn_agent(req: SpawnRequest):
    return await runner.spawn_agent(req)


@app.post("/api/agents/{session_id}/launch-terminal")
async def launch_terminal(session_id: str):
    session = runner.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")
    cwd_dir = session.worktree_path or str(config.WORKSPACE_BASE)
    cmd = session.terminal_command or f'& "{config.AGY_CLI_PATH}" --dangerously-skip-permissions -i "Work on Issue #{session.issue_number}"'
    ps_cmd = f'powershell -NoExit -Command "$host.ui.RawUI.WindowTitle = \'Antigravity CLI (agy) - Issue #{session.issue_number}\'; {cmd}"'
    subprocess.Popen(f'start {ps_cmd}', cwd=str(cwd_dir), shell=True)
    return {"status": "ok", "message": "Terminal launched", "command": cmd}

@app.post("/api/agents/{session_id}/resume")
async def resume_agent(session_id: str):
    success = await runner.resume_agent(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return {"status": "ok", "message": "Agent resumed successfully"}

@app.post("/api/agents/{session_id}/restart", response_model=AgentSessionInfo)
async def restart_agent(session_id: str):
    session = await runner.restart_agent(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return session

@app.post("/api/board/sync")
async def sync_board():
    try:
        for b in config.PROJECT_BOARD_IDS:
            await watcher._check_project_board(b)
        return {"status": "ok", "message": "Project board synced successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agents/{session_id}/interrupt")
async def interrupt_agent(session_id: str):
    success = await runner.interrupt_agent(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return {"status": "ok", "message": f"Agent {session_id} interrupted"}

@app.post("/api/agents/{session_id}/complete")
async def complete_agent(session_id: str):
    session = runner.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")
    
    key = f"{session.repo}#{session.issue_number}"
    if session.issue_number and key in watcher.item_id_map:
        await watcher.update_item_status(watcher.item_id_map[key], "done")

    success = await runner.complete_agent(session_id, reason="Manually marked as Done by user")
    return {"status": "ok", "message": f"Agent {session_id} marked as Done and archived"}

@app.post("/api/agents/{session_id}/compact")
async def compact_agent(session_id: str):
    session = runner.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")
    success = await runner.compact_session(session_id, force=True)
    return {"status": "ok", "message": f"Agent {session_id} chat compacted", "is_compacted": session.is_compacted}

@app.post("/api/agents/{session_id}/stop")
async def stop_agent(session_id: str, req: StopAgentRequest = StopAgentRequest()):
    success = await runner.stop_agent(session_id, req.reason or "Stopped via UI")
    if not success:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return {"status": "ok", "message": f"Agent {session_id} stopped"}

@app.post("/api/agents/{session_id}/context")
async def add_context(session_id: str, req: AddContextRequest):
    if not req.context.strip():
        raise HTTPException(status_code=400, detail="Context cannot be empty")
    success = await runner.add_context(session_id, req.context)
    if not success:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return {"status": "ok", "message": "Context injected successfully"}

@app.post("/api/webhooks/simulate")
async def simulate_webhook(req: SimulateWebhookRequest):
    """Simulates a GitHub Webhook event payload for local testing."""
    if req.event_type == "issues":
        mock_payload = {
            "action": req.action,
            "issue": {
                "number": req.issue_number,
                "title": req.issue_title,
                "body": req.issue_body,
                "labels": [{"name": req.label}]
            },
            "repository": {
                "full_name": req.repo
            }
        }
        prompt = (
            f"You have been assigned to GitHub Issue #{req.issue_number} in {req.repo}.\n\n"
            f"**Title**: {req.issue_title}\n\n"
            f"**Requirements / Description**:\n{req.issue_body}\n\n"
            f"**Operational Guidelines**:\n"
            f"- Work inside the designated branch and isolated worktree.\n"
            f"- Inspect existing code patterns before modifying.\n"
            f"- Follow AGENTS.md rules and keep documentation updated.\n"
            f"- When done, commit changes, open a pull request, and summarize your work."
        )
        spawn_req = SpawnRequest(
            repo=req.repo,
            issue_number=req.issue_number,
            title=req.issue_title,
            prompt=prompt
        )
        session = await runner.spawn_agent(spawn_req)
        return {"status": "ok", "simulated": True, "session": session}

    elif req.event_type == "issue_comment":
        mock_payload = {
            "action": req.action or "created",
            "issue": {
                "number": req.issue_number,
                "title": req.issue_title,
                "body": req.issue_body,
            },
            "comment": {
                "id": req.comment_id or 12345678,
                "body": req.comment_body or "Simulated feedback comment on issue.",
                "user": {"login": req.commenter or "reviewer"}
            },
            "repository": {
                "full_name": req.repo
            }
        }
        result = await process_github_event("issue_comment", mock_payload)
        return {"status": "ok", "simulated": True, "result": result}

    raise HTTPException(status_code=400, detail=f"Unsupported simulation event type: {req.event_type}")

# WebSocket for Real-Time Streaming
@app.websocket("/ws/agents")
async def websocket_agents(websocket: WebSocket):
    await websocket.accept()
    runner.register_ws(websocket)
    try:
        # Send current state immediately on connect
        sessions_data = [s.model_dump() for s in runner.list_sessions()]
        await websocket.send_json({"type": "init", "data": sessions_data})
        while True:
            # Keep socket alive and allow client to send ping or commands
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        runner.unregister_ws(websocket)
    except Exception:
        runner.unregister_ws(websocket)

# Mount Static UI Dashboard
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(STATIC_DIR / "index.html")
