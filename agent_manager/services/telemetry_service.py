"""
Telemetry & Agent Performance Analytics Service.
Calculates performance metrics and generates actionable optimization reports across sessions.
Adheres strictly to Anti-Monolith guidelines (< 250 lines).
"""

import logging
from typing import Dict, List, Any
from agent_manager.storage import load_sessions

logger = logging.getLogger("agent_manager.telemetry_service")


def compute_tool_frequencies(messages: List[Any]) -> Dict[str, int]:
    """Computes call frequency per tool name from session conversation messages."""
    freq: Dict[str, int] = {}
    for msg in messages:
        role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
        tool_name = getattr(msg, "tool_name", None) or (msg.get("tool_name") if isinstance(msg, dict) else None)
        if role == "TOOL_CALL" or tool_name:
            name = tool_name or "unknown"
            freq[name] = freq.get(name, 0) + 1
    return freq


def generate_optimization_reports() -> Dict[str, Any]:
    """
    Analyzes historical and active agent sessions to produce aggregate performance
    metrics and actionable optimization recommendations.
    """
    sessions_dict = load_sessions()
    sessions = list(sessions_dict.values())

    total_sessions = len(sessions)
    if total_sessions == 0:
        return {
            "summary": {
                "total_sessions": 0,
                "completed_sessions": 0,
                "failed_sessions": 0,
                "success_rate_percent": 0.0,
                "avg_duration_seconds": 0.0,
                "avg_turn_count": 0.0,
                "avg_tokens": 0.0,
                "total_tokens": 0,
            },
            "tool_usage": {},
            "recommendations": [],
            "session_performances": [],
        }

    completed_count = 0
    failed_count = 0
    total_duration = 0.0
    total_turns = 0
    total_tokens = 0
    global_tool_freq: Dict[str, int] = {}
    recommendations: List[Dict[str, Any]] = []
    session_performances: List[Dict[str, Any]] = []

    for s in sessions:
        # Attribute extraction compatible with dict or Pydantic model
        status = getattr(s, "status", None) or (s.get("status") if isinstance(s, dict) else "UNKNOWN")
        status_val = status.value if hasattr(status, "value") else str(status)
        
        session_id = getattr(s, "session_id", None) or (s.get("session_id") if isinstance(s, dict) else "")
        repo = getattr(s, "repo", None) or (s.get("repo") if isinstance(s, dict) else "unknown")
        issue_number = getattr(s, "issue_number", None) or (s.get("issue_number") if isinstance(s, dict) else None)
        title = getattr(s, "title", None) or (s.get("title") if isinstance(s, dict) else "")
        turns = getattr(s, "turn_count", None) or (s.get("turn_count", 0) if isinstance(s, dict) else 0)
        tokens = getattr(s, "total_tokens", None) or (s.get("total_tokens", 0) if isinstance(s, dict) else 0)
        duration = getattr(s, "duration_seconds", None) or (s.get("duration_seconds", 0.0) if isinstance(s, dict) else 0.0)
        cb_triggered = getattr(s, "circuit_breaker_triggered", None) or (s.get("circuit_breaker_triggered", False) if isinstance(s, dict) else False)
        dup_tools = getattr(s, "consecutive_duplicate_tool_count", None) or (s.get("consecutive_duplicate_tool_count", 0) if isinstance(s, dict) else 0)
        view_file_count = getattr(s, "consecutive_view_file_count", None) or (s.get("consecutive_view_file_count", 0) if isinstance(s, dict) else 0)
        messages = getattr(s, "messages", []) or (s.get("messages", []) if isinstance(s, dict) else [])

        # Counts
        if status_val in ["COMPLETED", "IN_REVIEW"]:
            completed_count += 1
        elif status_val in ["FAILED", "ERROR"] or cb_triggered:
            failed_count += 1

        total_duration += float(duration)
        total_turns += int(turns)
        total_tokens += int(tokens)

        # Tool frequencies
        s_tool_freq = compute_tool_frequencies(messages)
        for t_name, count in s_tool_freq.items():
            global_tool_freq[t_name] = global_tool_freq.get(t_name, 0) + count

        # Per-session summary
        session_performances.append({
            "session_id": session_id,
            "repo": repo,
            "issue_number": issue_number,
            "title": title,
            "status": status_val,
            "turn_count": turns,
            "total_tokens": tokens,
            "duration_seconds": round(duration, 1),
            "circuit_breaker_triggered": cb_triggered,
            "tool_calls_count": sum(s_tool_freq.values()),
        })

        # Optimization recommendations checks
        if cb_triggered:
            recommendations.append({
                "type": "circuit_breaker",
                "severity": "high",
                "session_id": session_id,
                "repo": repo,
                "issue_number": issue_number,
                "title": f"Circuit breaker tripped on {repo}#{issue_number or '?'}",
                "detail": f"Session exceeded guardrail limits (Turn limit / tool loop).",
                "action": "Break issue into smaller sub-issues or clarify prompt constraints in AGENTS.md."
            })
        if dup_tools >= 3:
            recommendations.append({
                "type": "duplicate_tool_loop",
                "severity": "medium",
                "session_id": session_id,
                "repo": repo,
                "issue_number": issue_number,
                "title": f"Repeated identical tool execution ({dup_tools} times)",
                "detail": f"Agent repeatedly invoked the same tool with identical parameters.",
                "action": "Encourage broader diagnostic searches or refine tool error messaging."
            })
        if view_file_count >= 8:
            recommendations.append({
                "type": "excessive_reads",
                "severity": "low",
                "session_id": session_id,
                "repo": repo,
                "issue_number": issue_number,
                "title": f"Excessive consecutive file reads ({view_file_count})",
                "detail": "Agent performed 8+ consecutive view_file operations without editing or testing.",
                "action": "Enforce search-first grep exploration directives to lower context token usage."
            })
        if turns >= 12:
            recommendations.append({
                "type": "high_turn_count",
                "severity": "medium",
                "session_id": session_id,
                "repo": repo,
                "issue_number": issue_number,
                "title": f"Approaching turn limit ({turns} turns)",
                "detail": "Task required close to the maximum 15 allowed turns before completion.",
                "action": "Ensure implementation plans provide granular architectural targets to accelerate execution."
            })

    # Sort session performances with newest/highest duration first
    session_performances.sort(key=lambda x: x["duration_seconds"], reverse=True)

    success_rate = (completed_count / total_sessions * 100.0) if total_sessions > 0 else 0.0
    avg_duration = (total_duration / total_sessions) if total_sessions > 0 else 0.0
    avg_turns = (total_turns / total_sessions) if total_sessions > 0 else 0.0
    avg_tokens = (total_tokens / total_sessions) if total_sessions > 0 else 0.0

    return {
        "summary": {
            "total_sessions": total_sessions,
            "completed_sessions": completed_count,
            "failed_sessions": failed_count,
            "success_rate_percent": round(success_rate, 1),
            "avg_duration_seconds": round(avg_duration, 1),
            "avg_turn_count": round(avg_turns, 1),
            "avg_tokens": round(avg_tokens, 0),
            "total_tokens": total_tokens,
        },
        "tool_usage": dict(sorted(global_tool_freq.items(), key=lambda item: item[1], reverse=True)),
        "recommendations": recommendations,
        "session_performances": session_performances[:50],
    }
