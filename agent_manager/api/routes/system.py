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


@router.get("/telemetry/manifesto-metrics")
async def get_manifesto_metrics():
    """Returns compliance metrics and health index across The Eight Pillars of the Agent Manager Manifesto."""
    from agent_manager.services.manifesto_metrics import generate_manifesto_compliance_report
    return generate_manifesto_compliance_report()


@router.get("/telemetry/code-health")
async def get_code_health():
    """Returns readability, simplicity, lines-of-code per file/function, and testability metrics."""
    from agent_manager.services.code_quality_service import generate_code_health_report
    return generate_code_health_report()


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


@router.get("/cron/progress-status")
async def get_progress_engine_status():
    """Returns status of the metric-driven autonomous progress engine."""
    from agent_manager.cron.progress_engine import progress_engine
    target = progress_engine.evaluate_next_target()
    return {
        "is_running": progress_engine.is_running,
        "last_check_at": progress_engine.last_check_at,
        "last_action": progress_engine.last_action,
        "next_metric_target": target,
        "history": progress_engine.history[-10:]
    }


@router.post("/cron/progress-now")
async def trigger_progress_advance(dry_run: bool = False):
    """Actively checks running agents: monitors if busy, or dispatches the next metric task if idle."""
    from agent_manager.cron.progress_engine import progress_engine
    return await progress_engine.check_and_advance(dry_run=dry_run)

