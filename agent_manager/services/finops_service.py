"""
FinOps & Dynamic Token Arbitrage Service.
Manages per-repository USD budget caps, spend tracking, threshold gating,
and automatic model downgrading (token arbitrage) at 80% budget utilization.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from agent_manager.services.cost_calculator_service import calculate_session_cost

logger = logging.getLogger("agent_manager.services.finops")


def get_budgets_file_path() -> Path:
    """Returns absolute path to the finops budgets configuration file."""
    repo_root = Path(__file__).resolve().parents[2]
    cfg_file = repo_root / "data" / "finops_budgets.json"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    return cfg_file


def load_budget_configurations() -> Dict[str, Dict[str, float]]:
    """Loads all per-repository budget limits from disk."""
    path = get_budgets_file_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Failed to read finops budgets: {e}")
        return {}


def save_budget_configurations(configs: Dict[str, Dict[str, float]]) -> None:
    """Persists per-repository budget limits to disk."""
    path = get_budgets_file_path()
    try:
        path.write_text(json.dumps(configs, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to save finops budgets: {e}")


def get_repo_budget(repo: str) -> Dict[str, float]:
    """Retrieves budget limits for a repository with standard defaults."""
    configs = load_budget_configurations()
    default_cfg = {"daily_limit_usd": 15.0, "monthly_limit_usd": 150.0, "arbitrage_threshold": 0.8}
    return configs.get(repo, default_cfg)


def set_repo_budget(repo: str, daily_limit: float, monthly_limit: float) -> Dict[str, float]:
    """Updates and saves budget limits for a repository."""
    configs = load_budget_configurations()
    configs[repo] = {
        "daily_limit_usd": max(1.0, float(daily_limit)),
        "monthly_limit_usd": max(5.0, float(monthly_limit)),
        "arbitrage_threshold": 0.8,
    }
    save_budget_configurations(configs)
    return configs[repo]


def evaluate_repo_spend(repo: str, sessions: List[Any]) -> Dict[str, Any]:
    """Computes daily and monthly spend for a repository and checks budget thresholds."""
    now = datetime.now(timezone.utc)
    today_spend = 0.0
    monthly_spend = 0.0

    for s in sessions:
        if getattr(s, "repo", "") != repo:
            continue
        cost = calculate_session_cost(s)
        # Parse timestamp
        created_str = getattr(s, "created_at", None)
        if created_str:
            try:
                dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                if dt.year == now.year and dt.month == now.month:
                    monthly_spend += cost
                    if dt.day == now.day:
                        today_spend += cost
            except Exception:
                today_spend += cost
                monthly_spend += cost

    budget = get_repo_budget(repo)
    daily_limit = budget["daily_limit_usd"]
    daily_utilization = round((today_spend / daily_limit) if daily_limit > 0 else 0.0, 3)

    is_exceeded = today_spend >= daily_limit or monthly_spend >= budget["monthly_limit_usd"]
    is_arbitrage = daily_utilization >= budget["arbitrage_threshold"]

    status = "EXCEEDED" if is_exceeded else ("ARBITRAGE" if is_arbitrage else "NORMAL")
    return {
        "repo": repo,
        "today_spend_usd": round(today_spend, 4),
        "monthly_spend_usd": round(monthly_spend, 4),
        "daily_limit_usd": daily_limit,
        "monthly_limit_usd": budget["monthly_limit_usd"],
        "daily_utilization": daily_utilization,
        "status": status,
        "allow_dispatch": not is_exceeded,
        "arbitrage_active": is_arbitrage,
    }


def apply_token_arbitrage(model: str, effort: str, repo: str, sessions: List[Any]) -> Tuple[str, str, bool]:
    """Downgrades model and effort to economical tiers if budget approaches limit."""
    eval_res = evaluate_repo_spend(repo, sessions)
    if eval_res["arbitrage_active"] or not eval_res["allow_dispatch"]:
        # Downgrade to cheap, high-speed flash model with low reasoning effort
        return ("gemini-2.5-flash", "low", True)
    return (model, effort, False)
