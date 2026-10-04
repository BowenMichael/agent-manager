import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from agent_manager.poller import LocalGitWatcher
from agent_manager.cron.updater import check_and_update_agent_manager
from agent_manager.cron.task_dispatcher import fetch_board_items, promote_backlog_issue
from agent_manager.config import GITHUB_PERSONAL_ACCESS_TOKEN

logger = logging.getLogger("agent_manager.cron.scheduler")


class ProjectBacklogDispatcher:
    _instance: Optional["ProjectBacklogDispatcher"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_dispatcher()
        return cls._instance

    def _init_dispatcher(self):
        self.watcher = LocalGitWatcher()
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.last_run_at: Optional[str] = None
        self.next_run_at: Optional[str] = None
        self.dispatch_history: List[Dict[str, Any]] = []

    async def check_and_update_agent_manager(self) -> Dict[str, Any]:
        return await check_and_update_agent_manager()

    async def check_and_dispatch(self) -> Dict[str, Any]:
        """
        1. FIRST THING: If no agents are running, checks if agent-manager is on latest version of main and updates it.
        2. Checks if any agents are actively running or initializing locally. If so, skips dispatch.
        3. Checks GitHub project boards for active issues in progress or ready for agent.
        4. If no active issues exist, takes one issue from the backlog and marks it 'Ready for Agent'.
        5. If backlog is empty, does nothing.
        """
        self.last_run_at = datetime.now(timezone.utc).isoformat()

        # Check local runner for active agents
        active_local_agents = []
        try:
            from agent_manager.runner import AgentRunnerManager
            from agent_manager.models import AgentStatus

            runner = AgentRunnerManager()
            for s in runner.list_sessions(include_archived=False):
                if s.status in (AgentStatus.RUNNING, AgentStatus.INITIALIZING):
                    active_local_agents.append(s.session_id)
            if getattr(runner, "_active_agents", None):
                for sid, proc in runner._active_agents.items():
                    if proc and getattr(proc, "returncode", None) is None:
                        if sid not in active_local_agents:
                            active_local_agents.append(sid)
        except Exception as e:
            logger.warning(f"[Cron Dispatcher] Could not inspect local agent sessions: {e}")

        if active_local_agents:
            msg = f"Local active agent(s) detected ({len(active_local_agents)} active: {active_local_agents}). Skipping backlog promotion."
            logger.info(f"[Cron Dispatcher] {msg}")
            result = {
                "status": "agents_running",
                "message": msg,
                "active_agent_count": len(active_local_agents),
                "active_agents": active_local_agents
            }
            self.dispatch_history.append({"timestamp": self.last_run_at, **result})
            return result

        update_result = await self.check_and_update_agent_manager()

        logger.info("[Cron Dispatcher] Checking project boards for active / ready issues...")

        if not GITHUB_PERSONAL_ACCESS_TOKEN:
            return {"status": "error", "message": "Missing GITHUB_PERSONAL_ACCESS_TOKEN", "update_result": update_result}

        try:
            active_items, backlog_items = await fetch_board_items()

            if active_items:
                active_desc = [f"#{x['issue_number']} ({x['status']})" for x in active_items]
                msg = f"Active issue(s) detected: {', '.join(active_desc)}. Skipping backlog promotion."
                logger.info(f"[Cron Dispatcher] {msg}")
                result = {
                    "status": "active_issue_present",
                    "message": msg,
                    "active_count": len(active_items),
                    "active_items": active_items,
                    "backlog_count": len(backlog_items)
                }
                self.dispatch_history.append({"timestamp": self.last_run_at, **result})
                return result

            if not backlog_items:
                msg = "No backlog items found across project boards. Nothing to dispatch."
                logger.info(f"[Cron Dispatcher] {msg}")
                result = {
                    "status": "backlog_empty",
                    "message": msg,
                    "active_count": 0,
                    "backlog_count": 0
                }
                self.dispatch_history.append({"timestamp": self.last_run_at, **result})
                return result

            chosen = backlog_items[0]
            success, msg = await promote_backlog_issue(self.watcher, chosen)

            if success:
                result = {
                    "status": "dispatched",
                    "message": msg,
                    "promoted_issue": chosen,
                    "remaining_backlog_count": len(backlog_items) - 1
                }
            else:
                result = {
                    "status": "error",
                    "message": msg,
                    "attempted_issue": chosen
                }

            self.dispatch_history.append({"timestamp": self.last_run_at, **result})
            return result

        except Exception as e:
            logger.error(f"[Cron Dispatcher] Unexpected error: {e}", exc_info=True)
            err_result = {"status": "error", "message": str(e)}
            self.dispatch_history.append({"timestamp": self.last_run_at, **err_result})
            return err_result

    async def start(self, initial_delay_seconds: int = 600, interval_seconds: int = 600):
        if self.is_running:
            logger.info("[Cron Dispatcher] Already running.")
            return

        self.is_running = True
        logger.info(
            f"[Cron Dispatcher] Started. Initial delay: {initial_delay_seconds}s "
            f"({initial_delay_seconds / 60:.1f} mins). Interval: {interval_seconds}s ({interval_seconds / 60:.1f} mins)."
        )

        async def _loop():
            next_dt = datetime.now(timezone.utc) + timedelta(seconds=initial_delay_seconds)
            self.next_run_at = next_dt.isoformat()
            logger.info(f"[Cron Dispatcher] Next run scheduled at: {self.next_run_at} UTC")

            try:
                await asyncio.sleep(initial_delay_seconds)
            except asyncio.CancelledError:
                self.is_running = False
                return

            while self.is_running:
                try:
                    await self.check_and_dispatch()
                except Exception as e:
                    logger.error(f"[Cron Dispatcher] Loop error: {e}")

                next_dt = datetime.now(timezone.utc) + timedelta(seconds=interval_seconds)
                self.next_run_at = next_dt.isoformat()
                logger.info(f"[Cron Dispatcher] Next run scheduled at: {self.next_run_at} UTC")

                try:
                    await asyncio.sleep(interval_seconds)
                except asyncio.CancelledError:
                    break

            self.is_running = False

        self._task = asyncio.create_task(_loop())

    def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()
        self.is_running = False
        self.next_run_at = None
        logger.info("[Cron Dispatcher] Stopped.")

    async def trigger_dispatch_now(self, delay_seconds: int = 5) -> Dict[str, Any]:
        """
        Non-blocking hook to schedule an immediate check_and_dispatch after an optional debounce delay.
        """
        if delay_seconds > 0:
            logger.info(f"[Cron Dispatcher] Trigger dispatch requested. Waiting {delay_seconds}s for state to settle...")
            await asyncio.sleep(delay_seconds)

        logger.info("[Cron Dispatcher] Executing triggered auto-dispatch check.")
        return await self.check_and_dispatch()
