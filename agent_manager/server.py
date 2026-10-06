import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from agent_manager.config import STATIC_DIR
from agent_manager.runner import AgentRunnerManager
from agent_manager.poller import LocalGitWatcher
from agent_manager.cron_dispatcher import dispatcher

from agent_manager.webhooks import router as webhooks_router
from agent_manager.api.files import router as files_router
from agent_manager.api.context import router as context_router
from agent_manager.api.settings import router as settings_router
from agent_manager.api.routes.system import router as system_router
from agent_manager.api.routes.agents import router as agents_router
from agent_manager.api.routes.github import router as github_routes_router
from agent_manager.api.routes.projects import router as projects_router
from agent_manager.api.routes.issues import router as issues_router
from agent_manager.api.routes.feedback import router as feedback_router
from agent_manager.api.routes.telemetry_cost import router as telemetry_cost_router
from agent_manager.api.routes.previews import router as previews_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("agent_manager.server")

watcher = LocalGitWatcher()
runner = AgentRunnerManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize relational database & auto-migrate legacy data
    try:
        from agent_manager.database import init_db
        init_db()
    except Exception as e:
        logger.warning(f"Failed to initialize database on startup: {e}")
    # Startup: Start local Git board watcher
    watcher.start()
    asyncio.create_task(runner.start_watchdog())
    # Startup: Reattach to any active independent background agent services
    runner.reattach_active_sessions()
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


# Include Sub-Routers
app.include_router(webhooks_router)
app.include_router(files_router)
app.include_router(context_router)
app.include_router(settings_router)
app.include_router(system_router)
app.include_router(agents_router)
app.include_router(github_routes_router)
app.include_router(projects_router)
app.include_router(issues_router)
app.include_router(feedback_router)
app.include_router(telemetry_cost_router)
app.include_router(previews_router)


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
