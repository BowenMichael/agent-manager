"""Formatters module."""
from agent_manager.formatters.comments import (
    format_agent_comment,
    format_agent_metadata_footer,
    is_agent_comment,
    BADGE_AUTONOMOUS_AGENT,
    BADGE_AGENT_UPDATE,
    BADGE_AGENT_TAKEOVER,
    BADGE_AGENT_PAUSED,
    FOOTER_SIGNATURE,
)

__all__ = [
    "format_agent_comment",
    "format_agent_metadata_footer",
    "is_agent_comment",
    "BADGE_AUTONOMOUS_AGENT",
    "BADGE_AGENT_UPDATE",
    "BADGE_AGENT_TAKEOVER",
    "BADGE_AGENT_PAUSED",
    "FOOTER_SIGNATURE",
]
