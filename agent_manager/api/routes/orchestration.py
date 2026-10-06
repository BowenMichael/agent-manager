"""
Cross-Repository Task Orchestration API Routes.
Exposes multi-repo coordination plans, contract drift detection, and PR linking.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agent_manager.services.cross_repo_orchestrator import (
    load_orchestration_plans,
    create_orchestration_plan,
    update_plan_pr_link
)

router = APIRouter(prefix="/api/orchestration", tags=["orchestration"])


class CreatePlanRequest(BaseModel):
    initiator_repo: str = Field(..., description="Repository initiating the change")
    initiator_issue: int = Field(..., description="Issue number in initiator repo")
    title: str = Field(..., description="Task title or contract summary")
    changed_files: List[str] = Field(default_factory=list, description="List of modified files")


class LinkPRsRequest(BaseModel):
    parent_pr_number: int = Field(..., description="Pull Request number in upstream repo")
    child_repo: str = Field(..., description="Downstream repository identifier")
    child_pr_number: int = Field(..., description="Pull Request number in child repo")


@router.get("/plans")
def list_orchestration_plans():
    """Returns all active and historical cross-repository orchestration plans."""
    plans = load_orchestration_plans()
    return {
        "count": len(plans),
        "plans": plans,
    }


@router.post("/plans")
def create_plan(payload: CreatePlanRequest):
    """Detects contract modifications, resolves downstream dependencies, and generates a plan."""
    try:
        plan = create_orchestration_plan(
            initiator_repo=payload.initiator_repo,
            initiator_issue=payload.initiator_issue,
            title=payload.title,
            changed_files=payload.changed_files
        )
        return {"status": "created", "plan": plan}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create orchestration plan: {e}")


@router.post("/plans/{plan_id}/link")
def link_pull_requests(plan_id: str, payload: LinkPRsRequest):
    """Links upstream and downstream PRs within an active orchestration plan."""
    updated = update_plan_pr_link(
        plan_id=plan_id,
        parent_pr=payload.parent_pr_number,
        child_repo=payload.child_repo,
        child_pr=payload.child_pr_number
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
    return {"status": "linked", "plan": updated}
