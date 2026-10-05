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

# Metric-to-Issue Priority Mapping
METRIC_ISSUE_MAP = [
    {
        "id": "feedback_flywheel_api",
        "repo": "BowenMichael/agent-manager",
        "issue_number": 102,
        "title": "[FLYWHEEL]: Universal Feedback Ingestion API & Project Board Auto-Placement",
        "condition": lambda cq, mf: not (Path(__file__).resolve().parents[2] / "agent_manager" / "api" / "routes" / "feedback.py").exists(),
        "reason": "Universal Feedback Flywheel API is missing; user feedback cannot automatically seed the agent queue."
    },
    {
        "id": "anti_monolith_refactor",
        "repo": "BowenMichael/agent-manager",
        "issue_number": 100,
        "title": "[REFACTOR]: Decompose Monolithic issues.py into Modular Route Controllers",
        "condition": lambda cq, mf: cq["readability_and_simplicity"]["max_lines_in_file"] > 250,
        "reason": "Source file exceeds 250 LOC limit (violates Section 5 Anti-Monolith)."
    },
    {
        "id": "stale_worktree_cleanup",
        "repo": "BowenMichael/agent-manager",
        "issue_number": 101,
        "title": "[GIT]: Autonomous Stale Worktree Pruner & Merge Lifecycle Manager",
        "condition": lambda cq, mf: not (Path(__file__).resolve().parents[2] / "agent_manager" / "services" / "worktree_cleaner.py").exists() and mf["pillars"]["II_isolation"].get("unmerged_worktrees_on_disk", 0) > 5,
        "reason": "Over 5 unmerged/stale worktrees detected on disk (violates Sacred Isolation)."
    },
    {
        "id": "long_file_filter",
        "repo": "BowenMichael/agent-manager",
        "issue_number": 39,
        "title": "[TASK]: avoid looking through long generated files",
        "condition": lambda cq, mf: not mf["pillars"]["III_anti_monolith"].get("long_file_filter_active", False),
        "reason": "Long generated file and binary circuit breaker is inactive."
    },
    {
        "id": "database_migration",
        "repo": "BowenMichael/agent-manager",
        "issue_number": 18,
        "title": "[DATA]: Migrate Session Storage from Flat JSON File to PostgreSQL / SQLite",
        "condition": lambda cq, mf: not mf["pillars"]["IV_process_decoupling"].get("relational_db_migrated", False),
        "reason": "Sessions still stored in flat JSON; relational persistence required."
    },
    {
        "id": "peer_reviewer_gateway",
        "repo": "BowenMichael/agent-manager",
        "issue_number": 90,
        "title": "[SWARM]: Automated Multi-Agent Peer Review & Security Audit Gateway",
        "condition": lambda cq, mf: not mf["pillars"]["V_cognitive_pipeline"].get("peer_reviewer_agent_active", False),
        "reason": "Adversarial PR Peer Reviewer persona is not yet configured."
    },
    {
        "id": "finops_budgeting",
        "repo": "BowenMichael/agent-manager",
        "issue_number": 93,
        "title": "[FINOPS]: Per-Repository Dollar Budgeting & Dynamic Token Arbitrage",
        "condition": lambda cq, mf: not mf["pillars"]["VI_swarm_concurrency"].get("per_repo_budget_caps", False),
        "reason": "Per-repository dollar budgeting caps are unconfigured."
    },
    {
        "id": "cost_estimator_and_replay",
        "repo": "BowenMichael/agent-manager",
        "issue_number": 95,
        "title": "[TELEMETRY]: Real-Time USD Cost Estimator & Session Execution Replay",
        "condition": lambda cq, mf: not mf["pillars"]["I_observability"].get("cost_tracking_active", False),
        "reason": "Real-time USD cost tracking and execution replays are inactive."
    }
]



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

        # 3. Promote & Dispatch
        try:
            from agent_manager.poller import LocalGitWatcher
            watcher = LocalGitWatcher()
            repo = next_target.get("repo", "BowenMichael/agent-manager")

            # Transition card to in_progress and notify
            await watcher.update_issue_status(repo, issue_num, "in_progress")
            
            result = {
                "status": "TASK_DISPATCHED",
                "timestamp": now_ts,
                "target_issue": issue_num,
                "target_title": title,
                "reason": reason,
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

