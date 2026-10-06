"""
Manifesto Compliance & Metric Evaluation Service.
Strictly measures production readiness against The Eight Pillars of Agent Manager.
Enforces realistic, enterprise multi-repo autonomous engineering standards.
Adheres strictly to Anti-Monolith guidelines (< 250 lines).
"""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from agent_manager.storage import load_sessions
from agent_manager.telemetry import load_telemetry_records


def evaluate_observability(sessions: List[Any], telemetry: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Pillar I: Radical Observability (Tokens, Live Cost in USD, Visual Replay)."""
    if not sessions:
        return {"score": 0.0, "status": "NO_SESSIONS"}

    total = len(sessions)
    tracked_tokens = sum(1 for s in sessions if (getattr(s, "total_tokens", 0) or 0) > 0)
    
    # Advanced Enterprise Criteria: Live USD Cost tracking, Session Video/DOM Replay
    has_cost_tracking = False  # Planned: USD cost tracking & model rate cards
    has_visual_replay = False  # Planned: WebP / DOM terminal execution replay

    score = (
        (tracked_tokens / total) * 20.0 +
        (10.0 if len(telemetry) > 50 else 0.0) +
        (35.0 if has_cost_tracking else 0.0) +
        (35.0 if has_visual_replay else 0.0)
    )
    return {
        "score": round(min(score, 100.0), 1),
        "token_tracking_active": round(tracked_tokens / total, 2),
        "cost_tracking_active": has_cost_tracking,
        "visual_replay_active": has_visual_replay
    }


def evaluate_isolation(sessions: List[Any], repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Pillar II: Sacred Isolation, Ephemeral Worktree Enclaves & Zero Merge Conflicts."""
    if not sessions:
        return {"score": 0.0, "status": "NO_SESSIONS"}

    isolated_count = sum(1 for s in sessions if ".worktrees" in (getattr(s, "worktree_path", "") or ""))
    root = repo_root or Path(__file__).resolve().parent.parent.parent
    if ".worktrees" in str(root):
        while root.name != "agent-manager" and root.parent != root:
            root = root.parent
    wt_dir = root / ".worktrees"
    stale_count = len([d for d in wt_dir.iterdir() if d.is_dir()]) if wt_dir.is_dir() else 0

    has_auto_pr_cleaner = (Path(__file__).resolve().parent / "worktree_cleaner.py").exists()
    has_multi_agent_rebase_resolver = False

    base = (isolated_count / len(sessions)) * 30.0
    stale_penalty = min(stale_count * 1.5, 20.0)
    score = max(0.0, base - stale_penalty + (35.0 if has_auto_pr_cleaner else 0.0) + (35.0 if has_multi_agent_rebase_resolver else 0.0))
    return {
        "score": round(score, 1),
        "isolated_sessions_ratio": round(isolated_count / len(sessions), 2),
        "unmerged_worktrees_on_disk": stale_count,
        "auto_cleaner_active": has_auto_pr_cleaner
    }


def evaluate_anti_monolith(target_dir: Optional[Path] = None, max_lines: int = 250) -> Dict[str, Any]:
    """Pillar III: Cognitive Hygiene, Semantic Cross-Repo Memory & Context Filters."""
    base = target_dir or Path(__file__).resolve().parent.parent
    files_checked = 0
    monoliths = []

    for root, _, files in os.walk(base):
        for f in files:
            if f.endswith(".py"):
                p = Path(root) / f
                try:
                    lines = len(p.read_text(encoding="utf-8").splitlines())
                    files_checked += 1
                    if lines > max_lines:
                        monoliths.append({"file": str(p.name), "lines": lines})
                except Exception:
                    continue

    loc_score = ((files_checked - len(monoliths)) / files_checked) * 30.0 if files_checked else 0.0
    has_semantic_memory = False  # Planned: Vector RAG across connected repos
    has_long_file_filter = (Path(__file__).resolve().parent / "file_filter_service.py").exists()

    score = loc_score + 10.0 + (30.0 if has_semantic_memory else 0.0) + (30.0 if has_long_file_filter else 0.0)
    return {
        "score": round(score, 1),
        "monoliths_detected": len(monoliths),
        "semantic_cross_repo_memory": has_semantic_memory,
        "long_file_filter_active": has_long_file_filter
    }


def evaluate_process_decoupling() -> Dict[str, Any]:
    """Pillar IV: Process Immortality & Cloud Mesh (PostgreSQL, Docker, Auth, Async Webhooks)."""
    root = Path(__file__).resolve().parent.parent.parent
    has_docker = (root / "Dockerfile").exists()
    has_render = (root / "render.yaml").exists()
    has_db_migration = (root / "agent_manager" / "database.py").exists() or "postgresql" in (root / "requirements.txt").read_text()
    has_auth = (root / "agent_manager" / "api" / "auth.py").exists()

    score = 15.0  # Local detached daemon exists
    if has_docker: score += 20.0
    if has_render: score += 15.0
    if has_db_migration: score += 30.0
    if has_auth: score += 20.0

    return {
        "score": round(score, 1),
        "detached_daemon": True,
        "dockerized": has_docker,
        "relational_db_migrated": has_db_migration,
        "auth_enabled": has_auth
    }


def evaluate_cognitive_pipeline() -> Dict[str, Any]:
    """Pillar V: Multi-Model Division of Labor & Multi-Agent Peer Review."""
    root = Path(__file__).resolve().parent.parent.parent
    has_stages = (root / "agent_manager" / "services" / "interpretation.py").exists()
    has_dynamic_handoff = False  # Planned: auto Stage 1 -> 2 -> 3 handoff
    has_peer_reviewer_agent = False  # Planned: Automated adversarial QA/Reviewer agent

    score = (15.0 if has_stages else 0.0) + (40.0 if has_dynamic_handoff else 0.0) + (45.0 if has_peer_reviewer_agent else 0.0)
    return {
        "score": round(score, 1),
        "interpretation_service": has_stages,
        "dynamic_handoff_active": has_dynamic_handoff,
        "peer_reviewer_agent_active": has_peer_reviewer_agent
    }


def evaluate_swarm_concurrency(sessions: List[Any]) -> Dict[str, Any]:
    """Pillar VI: Swarm Concurrency, Per-Repo Budget Caps & Coordinated Multi-Repo Changes."""
    repos = {getattr(s, "repo", "") for s in sessions if getattr(s, "repo", "")}
    has_budget_caps_per_repo = False  # Planned: $ token limits per repo
    has_cross_repo_coordinator = False  # Planned: Multi-repo coordinated atomic tasks

    score = (20.0 if len(repos) >= 3 else 10.0) + (40.0 if has_budget_caps_per_repo else 0.0) + (40.0 if has_cross_repo_coordinator else 0.0)
    return {
        "score": round(score, 1),
        "monitored_repositories": len(repos),
        "per_repo_budget_caps": has_budget_caps_per_repo,
        "cross_repo_coordination": has_cross_repo_coordinator
    }


def evaluate_ubiquitous_command() -> Dict[str, Any]:
    """Pillar VII: Ubiquitous Command (Mobile Expo App, Push Alerts, Workstation Bridge)."""
    root = Path(__file__).resolve().parent.parent.parent
    has_react = (root / "frontend" / "src" / "App.tsx").exists()
    has_voice = (root / "agent_manager" / "api" / "routes" / "issues.py").exists()
    has_expo_app = (root / "apps" / "mobile" / "app.json").exists() or (root / "mobile" / "package.json").exists()
    has_push_notifications = False
    has_workstation_bridge = (root / "agent_manager" / "bridge").exists()

    score = (10.0 if has_react else 0.0) + (10.0 if has_voice else 0.0)
    if has_expo_app: score += 30.0
    if has_push_notifications: score += 20.0
    if has_workstation_bridge: score += 30.0

    return {
        "score": round(score, 1),
        "desktop_react": has_react,
        "voice_intake": has_voice,
        "mobile_expo": has_expo_app,
        "push_alerts": has_push_notifications,
        "workstation_bridge": has_workstation_bridge
    }


def evaluate_accountability(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Pillar VIII: Deterministic Accountability, Ephemeral Preview QA & Release Engine."""
    root = repo_root or Path(__file__).resolve().parent.parent.parent
    has_changelog = (root / "CHANGELOG.md").exists()
    has_ci = (root / ".github" / "workflows" / "ci.yml").exists()
    has_release_engine = False  # Planned: Automated SemVer release tagging
    has_ephemeral_preview = False  # Planned: Auto deploy preview environment for PR

    score = (15.0 if has_changelog else 0.0) + (35.0 if has_ci else 0.0) + (25.0 if has_release_engine else 0.0) + (25.0 if has_ephemeral_preview else 0.0)
    return {
        "score": round(score, 1),
        "changelog_present": has_changelog,
        "ci_cd_active": has_ci,
        "semver_release_engine": has_release_engine,
        "ephemeral_preview_active": has_ephemeral_preview
    }


def generate_manifesto_compliance_report(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Generates complete quantitative compliance evaluation across all Eight Pillars."""
    sessions = list(load_sessions().values())
    telemetry = load_telemetry_records()

    pillars = {
        "I_observability": evaluate_observability(sessions, telemetry),
        "II_isolation": evaluate_isolation(sessions, repo_root),
        "III_anti_monolith": evaluate_anti_monolith(),
        "IV_process_decoupling": evaluate_process_decoupling(),
        "V_cognitive_pipeline": evaluate_cognitive_pipeline(),
        "VI_swarm_concurrency": evaluate_swarm_concurrency(sessions),
        "VII_ubiquitous_command": evaluate_ubiquitous_command(),
        "VIII_accountability": evaluate_accountability(repo_root),
    }

    weights = [0.15, 0.15, 0.15, 0.15, 0.10, 0.10, 0.10, 0.10]
    scores = [p["score"] for p in pillars.values()]
    overall = round(sum(w * s for w, s in zip(weights, scores)), 1)

    if overall >= 90.0: grade = "ENTERPRISE_SWARM"
    elif overall >= 75.0: grade = "PRODUCTION_READY"
    elif overall >= 50.0: grade = "ACTIVE_EXPANSION"
    elif overall >= 30.0: grade = "EARLY_FOUNDATION"
    else: grade = "GROUND_FLOOR"

    return {
        "manifesto_health_index": overall,
        "grade": grade,
        "target_baseline": "Enterprise Multi-Repo Swarm Standard (~20%)",
        "pillars": pillars,
        "summary": {
            "total_sessions_analyzed": len(sessions),
            "telemetry_records": len(telemetry),
            "uncompleted_vision_gap": round(100.0 - overall, 1)
        }
    }
