import sys
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from agent_manager.config import (
    GITHUB_PERSONAL_ACCESS_TOKEN, PROJECT_BOARD_IDS, PROJECT_BOARD_ID
)
from agent_manager.poller import LocalGitWatcher

logger = logging.getLogger("agent_manager.cron_dispatcher")

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

    async def check_and_dispatch(self) -> Dict[str, Any]:
        """
        Checks GitHub project boards for active issues in progress or ready for agent.
        If no active issues exist, takes one issue from the backlog and marks it 'Ready for Agent'.
        If backlog is empty, does nothing.
        """
        self.last_run_at = datetime.now(timezone.utc).isoformat()
        logger.info("[Cron Dispatcher] Checking project boards for active / ready issues...")

        if not GITHUB_PERSONAL_ACCESS_TOKEN:
            logger.warning("[Cron Dispatcher] No GitHub Personal Access Token configured. Skipping.")
            return {"status": "error", "message": "Missing GITHUB_PERSONAL_ACCESS_TOKEN"}

        query = """
        query($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              title
              items(first: 50) {
                nodes {
                  id
                  fieldValues(first: 10) {
                    nodes {
                      ... on ProjectV2ItemFieldSingleSelectValue {
                        name
                        optionId
                        field { ... on ProjectV2SingleSelectField { name id } }
                      }
                    }
                  }
                  content {
                    ... on Issue {
                      number
                      title
                      repository { nameWithOwner }
                    }
                  }
                }
              }
            }
          }
        }
        """

        headers = {
            "Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "AgentManagerCron/1.0"
        }

        active_items = []
        backlog_items = []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                for bid in PROJECT_BOARD_IDS:
                    resp = await client.post(
                        "https://api.github.com/graphql",
                        json={"query": query, "variables": {"projectId": bid}},
                        headers=headers
                    )
                    if resp.status_code != 200:
                        logger.warning("[Cron Dispatcher] GraphQL query failed for board %s: %s", bid, resp.status_code)
                        continue

                    node = resp.json().get("data", {}).get("node", {}) or {}
                    board_title = node.get("title", bid)
                    for item in node.get("items", {}).get("nodes", []):
                        content = item.get("content") or {}
                        status_name = None
                        for fv in item.get("fieldValues", {}).get("nodes", []):
                            if fv.get("field", {}).get("name") == "Status":
                                status_name = fv.get("name")
                                break

                        if not status_name or not content.get("number"):
                            continue

                        item_data = {
                            "item_id": item["id"],
                            "project_id": bid,
                            "board_title": board_title,
                            "issue_number": content.get("number"),
                            "title": content.get("title"),
                            "repo": (content.get("repository") or {}).get("nameWithOwner"),
                            "status": status_name
                        }

                        if "In Progress" in status_name or "Ready for Agent" in status_name:
                            active_items.append(item_data)
                        elif "Backlog" in status_name:
                            backlog_items.append(item_data)

            # Rule 1: Check if there is an active issue in progress or ready for agent
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

            # Rule 2: If there is not, check if backlog is empty
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

            # Rule 3: Take ONE issue out of the backlog and mark it 'Ready for Agent'
            chosen = backlog_items[0]
            success = await self.watcher.update_item_status(
                chosen["item_id"],
                "ready",
                project_id=chosen["project_id"]
            )

            if success:
                msg = f"Promoted Issue #{chosen['issue_number']} \"{chosen['title']}\" from [{chosen['board_title']}] Backlog to '📋 Ready for Agent'."
                logger.info(f"[Cron Dispatcher] 🚀 {msg}")
                result = {
                    "status": "dispatched",
                    "message": msg,
                    "promoted_issue": chosen,
                    "remaining_backlog_count": len(backlog_items) - 1
                }
            else:
                msg = f"Failed to update board status for Issue #{chosen['issue_number']}."
                logger.error(f"[Cron Dispatcher] ❌ {msg}")
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

    async def start(self, initial_delay_seconds: int = 1440, interval_seconds: int = 600):
        """
        Starts the recurring cron loop:
        1. Waits initial_delay_seconds (default: ~24 minutes, completing 32 mins from user prompt)
        2. Executes check_and_dispatch()
        3. Sleeps interval_seconds (default: 10 minutes) and repeats
        """
        if self.is_running:
            logger.info("[Cron Dispatcher] Already running.")
            return

        self.is_running = True
        logger.info(
            f"[Cron Dispatcher] Started. Initial delay: {initial_delay_seconds}s "
            f"({initial_delay_seconds / 60:.1f} mins). Interval: {interval_seconds}s ({interval_seconds / 60:.1f} mins)."
        )

        async def _loop():
            # Initial delay
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

dispatcher = ProjectBacklogDispatcher()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Autonomous Project Board Backlog Dispatcher")
    parser.add_argument("--run-now", action="store_true", help="Run once immediately and exit")
    parser.add_argument("--initial-delay", type=int, default=1440, help="Initial delay in seconds (default: 1440)")
    parser.add_argument("--interval", type=int, default=600, help="Recurring interval in seconds (default: 600)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if args.run_now:
        res = asyncio.run(dispatcher.check_and_dispatch())
        print("Result:", res)
    else:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(dispatcher.start(args.initial_delay, args.interval))
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            dispatcher.stop()
