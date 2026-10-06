"""
Dependencies and CVE Vulnerability Management API Routes.
Exposes scanning, auditing, and upgrade plan generation.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from agent_manager.runners.dependency_updater import (
    audit_repository_manifests,
    generate_upgrade_plan,
    VulnerabilityReport,
    DependencyUpgradePlan
)

router = APIRouter(prefix="/api/dependencies", tags=["dependencies"])


class AuditResponse(BaseModel):
    repo: str
    total_vulnerabilities: int
    vulnerabilities: List[VulnerabilityReport]


class PlanRequest(BaseModel):
    repo: Optional[str] = "BowenMichael/agent-manager"


@router.get("/audit", response_model=AuditResponse)
def audit_dependencies(repo_path: Optional[str] = None):
    """Scans repository manifests and returns detected CVE vulnerabilities."""
    target_path = Path(repo_path) if repo_path else Path.cwd()
    if not target_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Path '{target_path}' not found."
        )

    vulns = audit_repository_manifests(target_path)
    return AuditResponse(
        repo=target_path.name,
        total_vulnerabilities=len(vulns),
        vulnerabilities=vulns
    )


@router.post("/plan", response_model=DependencyUpgradePlan)
def create_upgrade_plan(req: PlanRequest):
    """Generates automated upgrade plan with markdown prompt for autonomous agents."""
    vulns = audit_repository_manifests(Path.cwd())
    return generate_upgrade_plan(req.repo or "BowenMichael/agent-manager", vulns)
