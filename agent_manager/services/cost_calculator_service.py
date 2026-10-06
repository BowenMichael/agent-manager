"""
Dynamic USD Cost Estimator & Model Rate Card Service.
Calculates real-time monetary cost for token consumption across model families,
burn velocities, and per-repository spend analytics.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import logging
from typing import Dict, Any, List, Optional
from agent_manager.models import AgentSessionInfo

logger = logging.getLogger("agent_manager.services.cost_calculator")

# Pricing in USD per 1 Million Tokens (Input, Output, Cached Read)
MODEL_RATE_CARDS: Dict[str, Dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30, "cached": 0.01875},
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00, "cached": 0.3125},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00, "cached": 0.3125},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30, "cached": 0.01875},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00, "cached": 0.30},
    "claude-3-haiku": {"input": 0.25, "output": 1.25, "cached": 0.025},
    "gpt-4o": {"input": 2.50, "output": 10.00, "cached": 1.25},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "cached": 0.075},
    "default": {"input": 1.00, "output": 4.00, "cached": 0.25},
}


def get_rate_card(model_name: Optional[str]) -> Dict[str, float]:
    """Retrieves pricing rates for a given model or default fallback."""
    if not model_name:
        return MODEL_RATE_CARDS["default"]

    clean_name = model_name.lower().strip()
    for key, rates in MODEL_RATE_CARDS.items():
        if key in clean_name or clean_name in key:
            return rates
    return MODEL_RATE_CARDS["default"]


def calculate_token_cost(
    model: Optional[str],
    input_tokens: int,
    output_tokens: int,
    thinking_tokens: int = 0,
    cache_read_tokens: int = 0
) -> float:
    """Calculates total dollar cost for token consumption rounded to 6 decimal places."""
    rates = get_rate_card(model)
    in_cost = (max(0, input_tokens) / 1_000_000.0) * rates["input"]
    out_tokens = max(0, output_tokens) + max(0, thinking_tokens)
    out_cost = (out_tokens / 1_000_000.0) * rates["output"]
    cache_cost = (max(0, cache_read_tokens) / 1_000_000.0) * rates["cached"]

    return round(in_cost + out_cost + cache_cost, 6)


def calculate_session_cost(session: AgentSessionInfo) -> float:
    """Calculates cumulative USD cost incurred by an agent session."""
    return calculate_token_cost(
        model=session.model,
        input_tokens=getattr(session, "input_tokens", 0) or 0,
        output_tokens=getattr(session, "output_tokens", 0) or 0,
        thinking_tokens=getattr(session, "thinking_tokens", 0) or 0,
        cache_read_tokens=getattr(session, "cache_read_tokens", 0) or 0
    )


def generate_cost_telemetry_summary(sessions: List[AgentSessionInfo]) -> Dict[str, Any]:
    """Computes fleet-wide financial metrics, repository breakdown, and hourly burn rate."""
    if not sessions:
        return {
            "total_spend_usd": 0.0,
            "cost_by_repo": {},
            "cost_by_model": {},
            "burn_rate_hourly_usd": 0.0,
            "avg_cost_per_session_usd": 0.0
        }

    total_cost = 0.0
    by_repo: Dict[str, float] = {}
    by_model: Dict[str, float] = {}
    total_duration_hours = 0.0

    for s in sessions:
        cost = calculate_session_cost(s)
        total_cost += cost

        repo_key = s.repo or "unassigned"
        by_repo[repo_key] = round(by_repo.get(repo_key, 0.0) + cost, 4)

        model_key = s.model or "default"
        by_model[model_key] = round(by_model.get(model_key, 0.0) + cost, 4)

        dur_sec = getattr(s, "duration_seconds", 0.0) or 0.0
        total_duration_hours += dur_sec / 3600.0

    burn_rate = round(total_cost / max(total_duration_hours, 1.0), 4) if total_duration_hours > 0 else round(total_cost, 4)

    return {
        "total_spend_usd": round(total_cost, 4),
        "cost_by_repo": by_repo,
        "cost_by_model": by_model,
        "burn_rate_hourly_usd": burn_rate,
        "avg_cost_per_session_usd": round(total_cost / len(sessions), 4)
    }
