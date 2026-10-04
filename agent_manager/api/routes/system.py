from fastapi import APIRouter
from agent_manager.cron_dispatcher import dispatcher

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/telemetry/tokens")
async def get_token_telemetry():
    """Returns aggregated token telemetry across multiple timescales (1h, 24h, 7d, 30d, all-time)."""
    from agent_manager.telemetry import get_timescale_metrics
    return get_timescale_metrics()


@router.get("/telemetry/reports")
async def get_telemetry_reports():
    """Returns agent execution performance metrics and actionable optimization reports."""
    from agent_manager.services.telemetry_service import generate_optimization_reports
    return generate_optimization_reports()


@router.get("/cron/status")
async def get_cron_status():
    return {
        "is_running": dispatcher.is_running,
        "is_paused": getattr(dispatcher, "is_paused", False),
        "last_run_at": dispatcher.last_run_at,
        "next_run_at": dispatcher.next_run_at,
        "history": dispatcher.dispatch_history[-10:]
    }


@router.post("/cron/dispatch-now")
async def trigger_cron_dispatch():
    return await dispatcher.check_and_dispatch()


@router.post("/cron/pause")
async def pause_cron():
    dispatcher.pause()
    return {
        "status": "ok",
        "is_paused": dispatcher.is_paused,
        "is_running": dispatcher.is_running,
        "message": "Cron scheduler paused."
    }


@router.post("/cron/resume")
async def resume_cron():
    dispatcher.resume()
    return {
        "status": "ok",
        "is_paused": dispatcher.is_paused,
        "is_running": dispatcher.is_running,
        "message": "Cron scheduler resumed."
    }
