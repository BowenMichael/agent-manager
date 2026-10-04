import asyncio
import logging
from typing import Optional

logger = logging.getLogger("agent_manager.services.dispatch_trigger")


def fire_dispatch_hook(delay_seconds: int = 5) -> Optional[asyncio.Task]:
    """
    Fires the autonomous auto-dispatch loop in the background after an optional delay.
    Called when an agent session completes, stops, or enters review.
    """
    try:
        from agent_manager.cron.scheduler import ProjectBacklogDispatcher

        dispatcher = ProjectBacklogDispatcher()
        task = asyncio.create_task(dispatcher.trigger_dispatch_now(delay_seconds=delay_seconds))
        logger.info(f"[Dispatch Trigger] Scheduled auto-dispatch check in {delay_seconds}s.")
        return task
    except Exception as e:
        logger.error(f"[Dispatch Trigger] Failed to schedule auto-dispatch: {e}")
        return None
