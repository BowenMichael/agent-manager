"""
Metric-to-Issue Priority Mapping and Targets.
Defines the autonomous sequence of backlog issues based on live telemetry and manifesto gaps.
Adheres strictly to Section 5 Anti-Monolith guidelines (< 150 LOC).
"""

from pathlib import Path
from typing import List, Dict, Any

REPO_ROOT = Path(__file__).resolve().parents[2]

METRIC_ISSUE_MAP: List[Dict[str, Any]] = [
    {
        "id": "feedback_flywheel_api",
        "repo": "BowenMichael/agent-manager",
        "issue_number": 102,
        "title": "[FLYWHEEL]: Universal Feedback Ingestion API & Project Board Auto-Placement",
        "condition": lambda cq, mf: not (REPO_ROOT / "agent_manager" / "api" / "routes" / "feedback.py").exists(),
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
        "condition": lambda cq, mf: not (REPO_ROOT / "agent_manager" / "services" / "worktree_cleaner.py").exists() and mf["pillars"]["II_isolation"].get("unmerged_worktrees_on_disk", 0) > 5,
        "reason": "Over 5 unmerged/stale worktrees detected on disk (violates Sacred Isolation)."
    },
    {
        "id": "long_file_filter",
        "repo": "BowenMichael/agent-manager",
        "issue_number": 39,
        "title": "[TASK]: avoid looking through long generated files",
        "condition": lambda cq, mf: not (REPO_ROOT / "agent_manager" / "services" / "file_filter_service.py").exists() or not mf["pillars"]["III_anti_monolith"].get("long_file_filter_active", False),
        "reason": "Long generated file and binary circuit breaker is inactive."
    },
    {
        "id": "database_migration",
        "repo": "BowenMichael/agent-manager",
        "issue_number": 18,
        "title": "[DATA]: Migrate Session Storage from Flat JSON File to PostgreSQL / SQLite",
        "condition": lambda cq, mf: not (REPO_ROOT / "agent_manager" / "database.py").exists() and not mf["pillars"]["IV_process_decoupling"].get("relational_db_migrated", False),
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
        "id": "usd_cost_estimator",
        "repo": "BowenMichael/agent-manager",
        "issue_number": 95,
        "title": "[TELEMETRY]: Real-Time USD Cost Estimator & Session Execution Replay",
        "condition": lambda cq, mf: not mf["pillars"]["I_observability"].get("cost_tracking_active", False),
        "reason": "Real-time USD cost tracking and execution replays are inactive."
    },
    {
        "id": "ephemeral_preview_environments",
        "repo": "BowenMichael/agent-manager",
        "issue_number": 91,
        "title": "[ENV]: Ephemeral Local Preview Environments & Live Tunnel Dispatch",
        "condition": lambda cq, mf: not (REPO_ROOT / "agent_manager" / "services" / "preview_env_service.py").exists(),
        "reason": "Ephemeral live preview environment dispatcher is not configured."
    },
    {
        "id": "cross_repo_semantic_memory",
        "repo": "BowenMichael/agent-manager",
        "issue_number": 92,
        "title": "[RAG]: Cross-Repository Semantic Code Intelligence & Vector Memory",
        "condition": lambda cq, mf: not mf["pillars"]["III_anti_monolith"].get("semantic_cross_repo_memory", False),
        "reason": "Semantic cross-repo vector memory is not yet indexed."
    },
    {
        "id": "multi_agent_rebase_resolver",
        "repo": "BowenMichael/agent-manager",
        "issue_number": 96,
        "title": "[GIT]: Autonomous Multi-Agent Git Rebase & Merge Conflict Auto-Resolver",
        "condition": lambda cq, mf: not mf["pillars"]["II_isolation"].get("has_multi_agent_rebase_resolver", False),
        "reason": "Autonomous git rebase conflict resolver is not yet active."
    }
]
