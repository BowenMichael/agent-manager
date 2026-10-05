"""
Metric-Driven Autonomous Progress Engine.
Continuously monitors active agent execution and automatically promotes the highest-priority
task based on live Code Health and Manifesto compliance metrics when the swarm is idle.
Adheres strictly to Anti-Monolith guidelines (< 250 lines).
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from agent_manager.cron.evaluator import inspect_active_local_agents
from agent_manager.services.code_quality_service import generate_code_health_report
from agent_manager.services.manifesto_metrics import generate_manifesto_compliance_report

logger = logging.getLogger("agent_manager.cron.progress_engine")

from agent_manager.cron.progress_targets import METRIC_ISSUE_MAP



class MetricDrivenProgressEngine:
    """Monitors active tasks and auto-advances the next metric-driven task when idle."""
    _instance: Optional["MetricDrivenProgressEngine"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_engine()
        return cls._instance

    def _init_engine(self):
        self.is_running = False
        self.last_check_at: Optional[str] = None
        self.last_action: Optional[Dict[str, Any]] = None
        self.history: List[Dict[str, Any]] = []

    def evaluate_next_target(self) -> Optional[Dict[str, Any]]:
        """Evaluates live metrics and returns the highest priority target task."""
        code_health = generate_code_health_report()
        manifesto = generate_manifesto_compliance_report()

        for item in METRIC_ISSUE_MAP:
            try:
                if item["condition"](code_health, manifesto):
                    return {
                        "issue_number": item["issue_number"],
                        "repo": item.get("repo", "BowenMichael/agent-manager"),
                        "title": item["title"],
                        "reason": item["reason"],
                        "metric_id": item["id"]
                    }
            except Exception as e:
                logger.warning(f"Error evaluating condition for {item['id']}: {e}")
                continue

        return None

    async def check_and_advance(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Core heartbeat:
        1. If an agent is running -> do nothing extra, let it keep working.
        2. If idle -> identify the next most relevant metric gap and advance it.
        """
        from datetime import datetime, timezone
        now_ts = datetime.now(timezone.utc).isoformat()
        self.last_check_at = now_ts

        # 1. Inspect running agents
        active_agents, active_issue_keys, in_review = inspect_active_local_agents()

        if active_agents:
            result = {
                "status": "BUSY",
                "timestamp": now_ts,
                "message": f"Active agent session(s) in progress ({', '.join(active_agents)}). Letting them run uninterrupted.",
                "active_agents": active_agents,
                "in_review_agents": in_review,
                "action": "MONITOR"
            }
            self.last_action = result
            self.history.append(result)
            logger.info(f"[Progress Engine] {result['message']}")
            return result

        # 2. Swarm is idle: determine next metric-driven priority
        next_target = self.evaluate_next_target()

        if not next_target:
            result = {
                "status": "HEALTHY_IDLE",
                "timestamp": now_ts,
                "message": "All primary code health and manifesto metrics are satisfied! Swarm is resting idle.",
                "action": "STANDBY"
            }
            self.last_action = result
            self.history.append(result)
            return result

        issue_num = next_target["issue_number"]
        title = next_target["title"]
        reason = next_target["reason"]

        logger.info(f"[Progress Engine] Idle detected. Next priority metric task: #{issue_num} ({title}). Reason: {reason}")

        if dry_run:
            result = {
                "status": "NEXT_TARGET_IDENTIFIED",
                "timestamp": now_ts,
                "target_issue": issue_num,
                "target_title": title,
                "reason": reason,
                "dry_run": True,
                "action": "PLANNED"
            }
            self.last_action = result
            self.history.append(result)
            return result

        # 3. Promote & Actively Dispatch Development
        try:
            import asyncio
            from agent_manager.runner import AgentRunnerManager
            from agent_manager.models import SpawnRequest
            from agent_manager.runners.supervisor import post_takeover_notice, sync_issue_board_status

            runner = AgentRunnerManager()
            repo = next_target.get("repo", "BowenMichael/agent-manager")

            # Transition card to in_progress
            await sync_issue_board_status(repo, issue_num, "in_progress")

            prompt = (
                f"You have been assigned to GitHub Issue #{issue_num} in {repo}.\n\n"
                f"**Title**: {title}\n\n"
                f"**Deficiency / Target**: {reason}\n\n"
                f"**Directives**:\n"
                f"1. Work strictly in your isolated worktree.\n"
                f"2. Follow AGENTS.md modular anti-monolith guidelines (< 250 LOC per file, <= 40 LOC per function).\n"
                f"3. MANDATORY: Update CHANGELOG.md with your changes before opening a PR or completing.\n"
                f"4. Run unit tests to verify before concluding."
            )
            spawn_req = SpawnRequest(
                repo=repo,
                issue_number=issue_num,
                title=title,
                prompt=prompt
            )
            session = await runner.spawn_agent(spawn_req)
            if session.worktree_path and session.git_branch:
                asyncio.create_task(post_takeover_notice(repo, issue_num, session.worktree_path, session.git_branch))

            result = {
                "status": "TASK_DISPATCHED",
                "timestamp": now_ts,
                "target_issue": issue_num,
                "target_title": title,
                "reason": reason,
                "session_id": session.session_id,
                "worktree": session.worktree_path,
                "branch": session.git_branch,
                "action": "ADVANCE"
            }
            self.last_action = result
            self.history.append(result)
            return result
        except Exception as e:
            logger.error(f"[Progress Engine] Failed to dispatch task #{issue_num}: {e}")
            err_result = {"status": "DISPATCH_FAILED", "error": str(e), "timestamp": now_ts}
            self.last_action = err_result
            return err_result

    async def start(self, interval_seconds: int = 180):
        """Runs the continuous heartbeat loop."""
        import asyncio
        self.is_running = True
        logger.info(f"[Progress Engine] Started continuous governor. Interval: {interval_seconds}s.")
        while self.is_running:
            try:
                await self.check_and_advance()
            except Exception as e:
                logger.error(f"[Progress Engine] Heartbeat error: {e}")
            await asyncio.sleep(interval_seconds)

    def stop(self):
        self.is_running = False
        logger.info("[Progress Engine] Stopped.")


progress_engine = MetricDrivenProgressEngine()


if __name__ == "__main__":
    import asyncio
    import argparse
    parser = argparse.ArgumentParser(description="Metric-Driven Autonomous Progress Engine")
    parser.add_argument("--now", action="store_true", help="Run single check-and-advance check and exit")
    parser.add_argument("--interval", type=int, default=180, help="Heartbeat interval in seconds (default: 180)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    if args.now:
        res = asyncio.run(progress_engine.check_and_advance())
        print("Progress Engine Result:", res)
    else:
        asyncio.run(progress_engine.start(args.interval))

