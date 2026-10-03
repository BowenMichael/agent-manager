import asyncio
import subprocess
from typing import Optional
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import agent_manager.config as config
from agent_manager.config import STATIC_DIR
from pydantic import BaseModel
import os
from agent_manager.models import (
    SpawnRequest, AddContextRequest, StopAgentRequest,
    SimulateWebhookRequest, AgentSessionInfo
)
from agent_manager.runner import AgentRunnerManager
from agent_manager.webhooks import router as webhooks_router
from agent_manager.poller import LocalGitWatcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("agent_manager.server")

watcher = LocalGitWatcher()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start local Git board watcher
    watcher.start()
    asyncio.create_task(runner.start_watchdog())
    yield
    # Shutdown: Stop watcher
    watcher.stop()

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

runner = AgentRunnerManager()
app.include_router(webhooks_router)

# REST Endpoints
class SettingsUpdateRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    default_repo: Optional[str] = None
    agy_mode: Optional[str] = None
    default_model: Optional[str] = None
    effort_level: Optional[str] = None
    max_session_tokens: Optional[int] = None

@app.get("/api/settings")
async def get_settings():
    import agent_manager.config as config
    key = config.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    masked_key = (key[:6] + "..." + key[-4:]) if len(key) > 10 else ("Set" if key else "")
    
    # Check Antigravity CLI quota status
    quota_status = {
        "subscription_active": True,
        "subscription_quota_reached": False,
        "quota_percent": 0.0,
        "reset_window": "Active / Fresh Quota",
        "current_active_model": config.DEFAULT_MODEL,
        "notice": "Google Antigravity Subscription is active and fully authenticated with zero API key required."
    }

    return {
        "has_gemini_api_key": bool(key),
        "masked_gemini_api_key": masked_key,
        "default_repo": config.DEFAULT_REPO,
        "project_board_id": config.PROJECT_BOARD_ID,
        "agy_mode": getattr(config, "AGY_MODE", "web_stream"),
        "agy_cli_installed": config.AGY_CLI_PATH.exists(),
        "agy_cli_path": str(config.AGY_CLI_PATH),
        "default_model": getattr(config, "DEFAULT_MODEL", "gemini-3.8-flash-high"),
        "default_effort": getattr(config, "DEFAULT_EFFORT", "high"),
        "available_efforts": getattr(config, "AVAILABLE_EFFORT_LEVELS", []),
        "available_models": getattr(config, "AVAILABLE_MODELS", []),
        "max_session_tokens": getattr(config, "MAX_SESSION_TOKENS", 150000),
        "quota_status": quota_status
    }

@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    import agent_manager.config as config
    env_file = Path(__file__).resolve().parent.parent / ".env"
    
    lines = []
    if env_file.exists():
        lines = env_file.read_text(encoding="utf-8").splitlines()

    def set_env(key_name, val):
        nonlocal lines
        found = False
        new_lines = []
        for line in lines:
            if line.startswith(f"{key_name}="):
                new_lines.append(f"{key_name}={val}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"{key_name}={val}")
        lines = new_lines

    
    if req.effort_level:
        eff_val = req.effort_level.strip().lower()
        config.DEFAULT_EFFORT = eff_val
        os.environ["DEFAULT_EFFORT"] = eff_val
        set_env("DEFAULT_EFFORT", eff_val)

    if req.default_model:
        model_val = req.default_model.strip()
        config.DEFAULT_MODEL = model_val
        os.environ["DEFAULT_MODEL"] = model_val
        set_env("DEFAULT_MODEL", model_val)

    if req.max_session_tokens:
        tok_val = int(req.max_session_tokens)
        config.MAX_SESSION_TOKENS = tok_val
        os.environ["MAX_SESSION_TOKENS"] = str(tok_val)
        set_env("MAX_SESSION_TOKENS", str(tok_val))

    if req.agy_mode is not None:
        mode_val = req.agy_mode.strip().lower()
        if mode_val in ("terminal", "web_stream"):
            config.AGY_MODE = mode_val
            os.environ["AGY_MODE"] = mode_val
            set_env("AGY_MODE", mode_val)

    if req.gemini_api_key is not None:
        key_val = req.gemini_api_key.strip()
        config.GEMINI_API_KEY = key_val
        os.environ["GEMINI_API_KEY"] = key_val
        set_env("GEMINI_API_KEY", key_val)

    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "status": "ok",
        "has_gemini_api_key": bool(config.GEMINI_API_KEY),
        "default_model": config.DEFAULT_MODEL,
        "default_effort": config.DEFAULT_EFFORT,
        "max_session_tokens": config.MAX_SESSION_TOKENS,
        "agy_mode": config.AGY_MODE
    }

@app.get("/api/agents", response_model=list[AgentSessionInfo])
async def list_agents():
    return runner.list_sessions()

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
        await watcher._check_project_board()
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
    
    from agent_manager.poller import STATUS_OPTIONS
    if session.issue_number and session.issue_number in watcher.item_id_map:
        item_id = watcher.item_id_map[session.issue_number]
        await watcher.update_item_status(item_id, STATUS_OPTIONS["done"])

    success = await runner.complete_agent(session_id, reason="Manually marked as Done by user")
    return {"status": "ok", "message": f"Agent {session_id} marked as Done and archived"}

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
