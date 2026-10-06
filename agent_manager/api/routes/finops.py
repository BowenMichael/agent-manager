"""
FinOps & Budget Management API Routes.
Exposes per-repo budget caps, spend evaluations, and token arbitrage thresholds.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agent_manager.storage import load_sessions
from agent_manager.services.finops_service import (
    load_budget_configurations, set_repo_budget, evaluate_repo_spend
)

router = APIRouter(prefix="/api/finops", tags=["finops"])


class BudgetUpdateRequest(BaseModel):
    repo: str = Field(..., min_length=1, description="Repository identifier (e.g. BowenMichael/fit-elo)")
    daily_limit_usd: float = Field(..., gt=0.0, description="Daily limit in USD")
    monthly_limit_usd: float = Field(..., gt=0.0, description="Monthly limit in USD")


@router.get("/budgets")
def get_all_repo_budgets():
    """Returns spend analysis, utilization, and budget status across all repositories."""
    sessions = list(load_sessions().values())
    repos = {getattr(s, "repo", "") for s in sessions if getattr(s, "repo", "")}
    configs = load_budget_configurations()
    repos.update(configs.keys())

    evaluations = []
    for r in sorted(list(repos)):
        if r:
            evaluations.append(evaluate_repo_spend(r, sessions))

    return {
        "count": len(evaluations),
        "budgets": evaluations,
    }


@router.post("/budgets")
def update_repo_budget(payload: BudgetUpdateRequest):
    """Sets daily and monthly USD budget limits for a repository."""
    try:
        updated = set_repo_budget(
            payload.repo,
            daily_limit=payload.daily_limit_usd,
            monthly_limit=payload.monthly_limit_usd
        )
        return {"status": "updated", "repo": payload.repo, "budget": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update budget: {e}")
