import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from agent_manager.poller import LocalGitWatcher
from agent_manager.cron.updater import check_and_update_agent_manager
from agent_manager.cron.task_dispatcher import (
    fetch_board_items,
    fetch_board_items_per_project,
    promote_backlog_issue,
)
from agent_manager.cron.evaluator import (
    inspect_active_local_agents,
    evaluate_and_dispatch_projects,
)
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
        from agent_manager import config
        self.watcher = LocalGitWatcher()
        self.is_running = False
        self.is_paused = getattr(config, "CRON_PAUSED", False)
        self._task: Optional[asyncio.Task] = None
        self.last_run_at: Optional[str] = None
        self.next_run_at: Optional[str] = None
        self.dispatch_history: List[Dict[str, Any]] = []

    def pause(self):
        self.is_paused = True
        logger.info("[Cron Dispatcher] Paused by user/system request.")
        self._persist_pause_state(True)

    def resume(self):
        self.is_paused = False
        logger.info("[Cron Dispatcher] Resumed.")
        self._persist_pause_state(False)

    def _persist_pause_state(self, paused: bool):
        try:
            import json
            from agent_manager.config import SETTINGS_FILE
            settings = {}
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f) or {}
            settings["cron_paused"] = paused
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not persist cron_paused setting: {e}")

    async def check_and_update_agent_manager(self) -> Dict[str, Any]:
        return await check_and_update_agent_manager()

    async def check_and_dispatch(self) -> Dict[str, Any]:
        """
        Evaluates active tasks on a per-project/board basis and promotes backlog items:
        1. Checks if agent-manager is on the latest version of main and updates it (if no agents running).
        2. Inspects local active agent sessions (running/initializing; IN_REVIEW agents do NOT count).
        3. Evaluates active issues and running agents per project board.
        4. If a project has no active work in progress, selects and promotes one issue from its backlog.
        5. Projects with active work are skipped without blocking idle projects.
        """
        if self.is_paused:
            logger.info("[Cron Dispatcher] Skipping evaluation: Cron scheduler is currently paused.")
            return {"status": "paused", "message": "Cron scheduler is paused."}

        self.last_run_at = datetime.now(timezone.utc).isoformat()

        active_local_agents, active_local_issue_keys, in_review_agents = inspect_active_local_agents()

        update_result = await self.check_and_update_agent_manager()

        logger.info("[Cron Dispatcher] Checking project boards for active / ready issues per project...")

        if not GITHUB_PERSONAL_ACCESS_TOKEN:
            return {"status": "error", "message": "Missing GITHUB_PERSONAL_ACCESS_TOKEN", "update_result": update_result}

        try:
            boards_data = await fetch_board_items_per_project()
            if not boards_data:
                res = await fetch_board_items()
                active_items, backlog_items = res[0], res[1]
                in_review_items = res[2] if len(res) > 2 else []
                boards_data = {}
                for item in active_items:
                    pid = item.get("project_id", "default")
                    if pid not in boards_data:
                        boards_data[pid] = {
                            "project_id": pid,
                            "board_title": item.get("board_title", pid),
                            "active_items": [],
                            "in_review_items": [],
                            "backlog_items": [],
                        }
                    boards_data[pid]["active_items"].append(item)
                for item in in_review_items:
                    pid = item.get("project_id", "default")
                    if pid not in boards_data:
                        boards_data[pid] = {
                            "project_id": pid,
                            "board_title": item.get("board_title", pid),
                            "active_items": [],
                            "in_review_items": [],
                            "backlog_items": [],
                        }
                    boards_data[pid]["in_review_items"].append(item)
                for item in backlog_items:
                    pid = item.get("project_id", "default")
                    if pid not in boards_data:
                        boards_data[pid] = {
                            "project_id": pid,
                            "board_title": item.get("board_title", pid),
                            "active_items": [],
                            "in_review_items": [],
                            "backlog_items": [],
                        }
                    boards_data[pid]["backlog_items"].append(item)

            result = await evaluate_and_dispatch_projects(
                boards_data,
                active_local_issue_keys,
                self.watcher,
                promote_backlog_issue
            )
            result["in_review_local_agents"] = in_review_agents
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
