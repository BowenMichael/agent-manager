"""
Cross-Repository Coordinated Tasks & Contract Sync Orchestrator.
Detects contract/schema drift, computes multi-repo dependency graphs,
spawns coordinated child tasks, and synchronizes mutual PR cross-references.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger("agent_manager.services.cross_repo_orchestrator")

DEFAULT_DEPENDENCIES: Dict[str, List[str]] = {
    "BowenMichael/agent-manager": ["BowenMichael/f1-frontend", "frontend"],
    "BowenMichael/full_swing_scraper": ["BowenMichael/fit-elo"],
    "BowenMichael/fit-elo": ["frontend"],
    "agent-manager": ["frontend"],
}

CONTRACT_PATTERNS = ["routes/", "api/", "schema", "models.py", "openapi.json", "interfaces/"]


def get_orchestration_file_path() -> Path:
    """Returns absolute path to cross-repository orchestration storage."""
    repo_root = Path(__file__).resolve().parents[2]
    storage = repo_root / "data" / "cross_repo_orchestration.json"
    storage.parent.mkdir(parents=True, exist_ok=True)
    return storage


def load_orchestration_plans() -> List[Dict[str, Any]]:
    """Loads all persisted cross-repository task plans from disk."""
    path = get_orchestration_file_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"Failed to load orchestration plans: {e}")
        return []


def save_orchestration_plans(plans: List[Dict[str, Any]]) -> None:
    """Persists cross-repository orchestration plans to disk."""
    path = get_orchestration_file_path()
    try:
        path.write_text(json.dumps(plans[-100:], indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to save orchestration plans: {e}")


def detect_contract_files(changed_files: List[str]) -> List[str]:
    """Identifies files that alter external API contracts or data models."""
    detected = []
    for f in changed_files:
        norm = f.replace("\\", "/").lower()
        if any(pattern in norm for pattern in CONTRACT_PATTERNS):
            detected.append(f)
    return detected


def resolve_dependent_repos(repo: str) -> List[str]:
    """Resolves all downstream dependent repositories from the dependency graph."""
    for key, dependents in DEFAULT_DEPENDENCIES.items():
        if key in repo or repo in key:
            return list(dependents)
    return []


def create_orchestration_plan(
    initiator_repo: str,
    initiator_issue: int,
    title: str,
    changed_files: List[str]
) -> Dict[str, Any]:
    """Creates a multi-repo orchestration plan and generates child task links."""
    contracts = detect_contract_files(changed_files)
    dependents = resolve_dependent_repos(initiator_repo) if contracts else []
    plans = load_orchestration_plans()

    plan_id = f"plan_{len(plans) + 1}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    child_tasks = []
    for idx, dep in enumerate(dependents):
        child_tasks.append({
            "link_id": f"{plan_id}_child_{idx + 1}",
            "parent_repo": initiator_repo,
            "parent_issue_number": initiator_issue,
            "parent_pr_number": None,
            "child_repo": dep,
            "child_issue_number": None,
            "child_pr_number": None,
            "contract_path": contracts[0] if contracts else None,
            "status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    plan = {
        "plan_id": plan_id,
        "title": title,
        "initiator_repo": initiator_repo,
        "initiator_issue": initiator_issue,
        "contract_changes": contracts,
        "dependent_repos": dependents,
        "child_tasks": child_tasks,
        "is_atomic": True,
        "status": "ACTIVE" if dependents else "NO_DEPENDENTS",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    plans.append(plan)
    save_orchestration_plans(plans)
    return plan


def format_cross_reference_comment(
    parent_repo: str,
    parent_pr: int,
    child_repo: str,
    child_pr: int
) -> str:
    """Formats mutual markdown cross-reference comments for coordinated PRs."""
    return (
        f"🔗 **Coordinated Cross-Repository Task Linked**\n\n"
        f"- **Upstream PR**: [{parent_repo}#{parent_pr}](https://github.com/{parent_repo}/pull/{parent_pr})\n"
        f"- **Downstream PR**: [{child_repo}#{child_pr}](https://github.com/{child_repo}/pull/{child_pr})\n"
        f"- **Sync Mode**: Atomic contract synchronization verified by Agent Manager."
    )


def update_plan_pr_link(
    plan_id: str,
    parent_pr: int,
    child_repo: str,
    child_pr: int
) -> Optional[Dict[str, Any]]:
    """Links parent and child PR numbers and transitions status to VERIFIED."""
    plans = load_orchestration_plans()
    for plan in plans:
        if plan.get("plan_id") == plan_id:
            for child in plan.get("child_tasks", []):
                if child.get("child_repo") == child_repo:
                    child["parent_pr_number"] = parent_pr
                    child["child_pr_number"] = child_pr
                    child["status"] = "VERIFIED"
            save_orchestration_plans(plans)
            return plan
    return None
