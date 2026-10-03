import subprocess
from typing import Optional
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

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

@app.get("/api/settings")
async def get_settings():
    from agent_manager import config
    key = config.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    masked_key = (key[:6] + "..." + key[-4:]) if len(key) > 10 else ("Set" if key else "")
    return {
        "has_gemini_api_key": bool(key),
        "masked_gemini_api_key": masked_key,
        "default_repo": config.DEFAULT_REPO,
        "project_board_id": config.PROJECT_BOARD_ID,
        "agy_mode": getattr(config, "AGY_MODE", "terminal"),
        "agy_cli_installed": config.AGY_CLI_PATH.exists(),
        "agy_cli_path": str(config.AGY_CLI_PATH)
    }

@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    import agent_manager.config as config
    env_file = Path(__file__).resolve().parent.parent / ".env"
    
    lines = []
    if env_file.exists():
        lines = env_file.read_text(encoding="utf-8").splitlines()

    if req.agy_mode is not None:
        mode_val = req.agy_mode.strip().lower()
        if mode_val in ("terminal", "web_stream"):
            config.AGY_MODE = mode_val
            os.environ["AGY_MODE"] = mode_val
            # Update .env
            found = False
            new_lines = []
            for line in lines:
                if line.startswith("AGY_MODE="):
                    new_lines.append(f"AGY_MODE={mode_val}")
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(f"AGY_MODE={mode_val}")
            lines = new_lines

    if req.gemini_api_key is not None:
        key_val = req.gemini_api_key.strip()
        config.GEMINI_API_KEY = key_val
        os.environ["GEMINI_API_KEY"] = key_val
        found = False
        new_lines = []
        for line in lines:
            if line.startswith("GEMINI_API_KEY="):
                new_lines.append(f"GEMINI_API_KEY={key_val}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"GEMINI_API_KEY={key_val}")
        lines = new_lines

    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "status": "ok",
        "has_gemini_api_key": bool(config.GEMINI_API_KEY),
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
