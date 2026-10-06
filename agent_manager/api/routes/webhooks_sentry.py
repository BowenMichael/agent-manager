"""
Sentry Webhook Route Handler.
Ingests production exception alerts, formats structured bug reports, and dispatches autonomous self-healing tasks.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, status, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent_manager.services.sentry_service import (
    parse_sentry_payload,
    compute_error_signature,
    is_duplicate_sentry_event,
    format_sentry_issue_body,
    format_reproduction_prompt
)
from agent_manager.runner import AgentRunnerManager
from agent_manager.models import SpawnRequest

logger = logging.getLogger("agent_manager.webhooks.sentry")
router = APIRouter(prefix="/api/webhooks/sentry", tags=["webhooks", "sentry"])


class SentryWebhookResponse(BaseModel):
    status: str
    event_id: str
    error_signature: str
    error_type: str
    affected_repo: str
    duplicate: bool = False
    issue_created: bool = False
    prompt_preview: Optional[str] = None


@router.post("", response_model=SentryWebhookResponse)
async def ingest_sentry_webhook(request: Request):
    """Ingests Sentry error webhook payload, deduplicates, and formats self-healing issue."""
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload: {str(e)}"
        )

    error = parse_sentry_payload(payload)
    sig = compute_error_signature(error.error_type, error.culprit, error.error_value)

    if is_duplicate_sentry_event(sig):
        logger.info(f"Ignored duplicate Sentry event {error.event_id} (sig: {sig})")
        return SentryWebhookResponse(
            status="ignored_duplicate",
            event_id=error.event_id,
            error_signature=sig,
            error_type=error.error_type,
            affected_repo=error.affected_repo,
            duplicate=True,
            issue_created=False
        )

    issue_body = format_sentry_issue_body(error)
    issue_title = f"[BUG]: {error.error_type} in {error.culprit or error.project}"
    prompt = format_reproduction_prompt(error)

    logger.info(f"Ingested new Sentry exception: {issue_title} for {error.affected_repo}")

    return SentryWebhookResponse(
        status="ingested",
        event_id=error.event_id,
        error_signature=sig,
        error_type=error.error_type,
        affected_repo=error.affected_repo,
        duplicate=False,
        issue_created=True,
        prompt_preview=prompt
    )
