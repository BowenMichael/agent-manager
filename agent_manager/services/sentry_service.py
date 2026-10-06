"""
Sentry Exception Ingestion & Autonomous Bug Reproduction Service.
Parses Sentry webhook events, extracts stack traces and breadcrumbs, and formats issues.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import hashlib
import json
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

logger = logging.getLogger("agent_manager.sentry")

# In-memory deduplication cache
_SEEN_EVENT_SIGNATURES = set()


class SentryFrame(BaseModel):
    filename: str = ""
    function: str = ""
    lineno: Optional[int] = None
    colno: Optional[int] = None
    in_app: bool = True
    context_line: Optional[str] = None


class SentryErrorDetails(BaseModel):
    event_id: str
    project: str
    culprit: str = ""
    error_type: str = "Exception"
    error_value: str = ""
    affected_repo: str = "BowenMichael/agent-manager"
    stacktrace_frames: List[SentryFrame] = Field(default_factory=list)
    breadcrumbs: List[Dict[str, Any]] = Field(default_factory=list)
    environment: str = "production"
    url: Optional[str] = None


def compute_error_signature(error_type: str, culprit: str, error_value: str) -> str:
    """Computes a deterministic MD5 signature to prevent duplicate issue creation."""
    raw = f"{error_type}:{culprit}:{error_value}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def is_duplicate_sentry_event(signature: str) -> bool:
    """Checks and records error signature for deduplication."""
    if signature in _SEEN_EVENT_SIGNATURES:
        return True
    _SEEN_EVENT_SIGNATURES.add(signature)
    return False


def parse_sentry_payload(payload: Dict[str, Any], default_repo: str = "BowenMichael/agent-manager") -> SentryErrorDetails:
    """Parses Sentry webhook JSON payload into structured error details."""
    event = payload.get("event", payload)
    event_id = str(event.get("event_id", payload.get("id", "unknown_id")))
    project = str(payload.get("project_name", payload.get("project", "default-app")))
    culprit = event.get("culprit", "")

    # Extract exception details
    exceptions = event.get("exception", {}).get("values", [])
    exc = exceptions[0] if exceptions else {}
    error_type = exc.get("type", event.get("title", "RuntimeError"))
    error_value = exc.get("value", event.get("message", ""))

    # Extract stacktrace frames
    raw_frames = exc.get("stacktrace", {}).get("frames", [])
    frames = [
        SentryFrame(
            filename=f.get("filename", ""),
            function=f.get("function", ""),
            lineno=f.get("lineno"),
            colno=f.get("colno"),
            in_app=f.get("in_app", True),
            context_line=f.get("context_line")
        )
        for f in raw_frames
    ]

    breadcrumbs = event.get("breadcrumbs", {}).get("values", [])
    env = event.get("environment", "production")
    url = payload.get("url") or event.get("web_url")

    # Map project to repository name if known
    repo_map = {
        "agent-manager": "BowenMichael/agent-manager",
        "fitelo": "BowenMichael/fitelo",
        "better-business-deal": "BowenMichael/better_buisness_deal",
        "leanfolio": "BowenMichael/leanfolio",
        "f1-frontend": "BowenMichael/f1-frontend",
    }
    affected_repo = repo_map.get(project.lower(), default_repo)

    return SentryErrorDetails(
        event_id=event_id,
        project=project,
        culprit=culprit,
        error_type=error_type,
        error_value=error_value,
        affected_repo=affected_repo,
        stacktrace_frames=frames,
        breadcrumbs=breadcrumbs[-10:],
        environment=env,
        url=url
    )


def format_sentry_issue_body(error: SentryErrorDetails) -> str:
    """Formats rich markdown issue body with reproduction instructions for autonomous agents."""
    lines = [
        f"### 🚨 Production Exception: `{error.error_type}`",
        "",
        f"**Project**: `{error.project}` | **Environment**: `{error.environment}` | **Event ID**: `{error.event_id}`",
        f"**Culprit / Location**: `{error.culprit or 'Unknown'}`",
        "",
        "#### Error Message",
        "```text",
        f"{error.error_type}: {error.error_value}",
        "```",
        "",
        "#### 📋 Acceptance Criteria",
        "- [ ] Replicate the exception in an isolated unit or integration test.",
        "- [ ] Implement bug fix resolving the root cause without regressions.",
        "- [ ] Confirm 100% test pass rate.",
        "- [ ] Update `CHANGELOG.md` and submit verified Pull Request.",
        "",
        "#### 🔍 Stack Trace Details",
        "<details><summary>Click to expand stack trace frames</summary>",
        "",
        "```text"
    ]
    for frame in error.stacktrace_frames[-8:]:
        loc = f"{frame.filename}:{frame.lineno}" if frame.lineno else frame.filename
        lines.append(f"  File \"{loc}\", in {frame.function}")
        if frame.context_line:
            lines.append(f"    {frame.context_line.strip()}")
    lines.extend([
        "```",
        "</details>",
        "",
        "---",
        "*Captured automatically by Agent Manager Sentry Gateway*"
    ])
    return "\n".join(lines)


def format_reproduction_prompt(error: SentryErrorDetails, issue_number: Optional[int] = None) -> str:
    """Generates execution prompt instructing autonomous agents to reproduce and heal the bug."""
    issue_ref = f"Issue #{issue_number}" if issue_number else "the captured exception"
    return (
        f"You are assigned to autonomously reproduce and fix {issue_ref} in `{error.affected_repo}`.\n\n"
        f"**Error**: `{error.error_type}: {error.error_value}`\n"
        f"**Culprit**: `{error.culprit}`\n\n"
        "**Instructions**:\n"
        "1. Write an isolated reproduction test asserting the failure condition.\n"
        "2. Apply the necessary code fix to resolve the root cause.\n"
        "3. Verify all unit tests pass with 100% success.\n"
        "4. Update `CHANGELOG.md` under `## [Unreleased]` / `### Fixed`."
    )
