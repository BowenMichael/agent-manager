"""
Autonomous CVE & Library Upgrade Engine (Dependabot++).
Scans dependencies, audits for CVEs/outdated packages, and manages upgrade workflows.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("agent_manager.dependency_updater")


class VulnerabilityReport(BaseModel):
    package_name: str
    current_version: str
    fixed_version: str
    severity: str = "medium"
    cve_id: Optional[str] = None
    advisory_url: Optional[str] = None
    manifest_file: str
    ecosystem: str = "pip"  # "pip" | "npm"


class DependencyUpgradePlan(BaseModel):
    repo: str
    vulnerabilities: List[VulnerabilityReport] = Field(default_factory=list)
    branch_name: str
    total_cves: int = 0
    instructions: str = ""


def parse_pip_requirements(content: str) -> Dict[str, str]:
    """Parses standard requirements.txt content into package -> version specifier map."""
    packages = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([a-zA-Z0-9_\-\[\]]+)\s*([=><~^!].*)?$", line)
        if match:
            pkg = match.group(1).strip()
            ver = match.group(2).strip() if match.group(2) else "*"
            packages[pkg] = ver
    return packages


def parse_package_json_dependencies(content: str) -> Dict[str, str]:
    """Parses package.json dependencies and devDependencies into a merged map."""
    try:
        data = json.loads(content)
        deps = data.get("dependencies", {})
        dev_deps = data.get("devDependencies", {})
        return {**deps, **dev_deps}
    except Exception:
        return {}


def evaluate_vulnerability(
    package: str,
    current_spec: str,
    manifest: str,
    known_cves: Optional[Dict[str, Dict[str, Any]]] = None
) -> Optional[VulnerabilityReport]:
    """Evaluates if a package matches a known vulnerability advisory."""
    if not known_cves:
        # Default security advisory database table
        known_cves = {
            "requests": {"fixed": ">=2.31.0", "cve": "CVE-2023-32681", "severity": "medium", "eco": "pip"},
            "urllib3": {"fixed": ">=2.0.7", "cve": "CVE-2023-45803", "severity": "high", "eco": "pip"},
            "axios": {"fixed": ">=1.7.4", "cve": "CVE-2024-39338", "severity": "high", "eco": "npm"},
            "semver": {"fixed": ">=7.5.2", "cve": "CVE-2022-25883", "severity": "medium", "eco": "npm"},
        }

    pkg_key = package.lower().split("[")[0]
    if pkg_key in known_cves:
        info = known_cves[pkg_key]
        return VulnerabilityReport(
            package_name=package,
            current_version=current_spec,
            fixed_version=info["fixed"],
            severity=info["severity"],
            cve_id=info["cve"],
            manifest_file=manifest,
            ecosystem=info["eco"]
        )
    return None


def audit_repository_manifests(repo_root: Path) -> List[VulnerabilityReport]:
    """Scans repository root for manifest files and identifies known vulnerabilities."""
    vulns: List[VulnerabilityReport] = []

    # Check requirements.txt
    req_path = repo_root / "requirements.txt"
    if req_path.exists():
        text = req_path.read_text(encoding="utf-8", errors="ignore")
        for pkg, ver in parse_pip_requirements(text).items():
            report = evaluate_vulnerability(pkg, ver, "requirements.txt")
            if report:
                vulns.append(report)

    # Check package.json
    pkg_path = repo_root / "package.json"
    if pkg_path.exists():
        text = pkg_path.read_text(encoding="utf-8", errors="ignore")
        for pkg, ver in parse_package_json_dependencies(text).items():
            report = evaluate_vulnerability(pkg, ver, "package.json")
            if report:
                vulns.append(report)

    return vulns


def generate_upgrade_plan(repo: str, vulns: List[VulnerabilityReport]) -> DependencyUpgradePlan:
    """Constructs autonomous upgrade plan and execution prompt for agent swarm."""
    branch = f"feat/dependabot-upgrade-{len(vulns)}-cves"
    instructions = [
        f"### 🛡️ Dependency Upgrade & Security Patching Plan for `{repo}`",
        "",
        f"Found **{len(vulns)}** vulnerable package(s) requiring immediate updates:",
        ""
    ]
    for v in vulns:
        cve_str = f" ({v.cve_id})" if v.cve_id else ""
        instructions.append(f"- **{v.package_name}** (`{v.current_version}` ➔ `{v.fixed_version}`) in `{v.manifest_file}` [Severity: {v.severity.upper()}]{cve_str}")

    instructions.extend([
        "",
        "#### 📋 Instructions for Autonomous Upgrade Agent:",
        "1. Update the version specifier in the relevant manifest file.",
        "2. Run the unit and integration test suites with log suppression.",
        "3. If tests break due to deprecated API calls, refactor code to the updated API.",
        "4. Update `CHANGELOG.md` under `## [Unreleased]` / `### Security`.",
        "5. Open a verified Pull Request."
    ])

    return DependencyUpgradePlan(
        repo=repo,
        vulnerabilities=vulns,
        branch_name=branch,
        total_cves=len(vulns),
        instructions="\n".join(instructions)
    )
