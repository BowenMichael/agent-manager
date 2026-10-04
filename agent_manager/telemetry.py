"""
Token Telemetry & Timescale Analytics Service.
Tracks token consumption across granular timescales (hourly, daily, weekly, monthly, all-time),
broken down by model, repository, and task lifecycle.
Adheres to Section 5 Anti-Monolith rules (< 250 lines).
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger("agent_manager.telemetry")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TELEMETRY_FILE = DATA_DIR / "telemetry_tokens.json"

def get_telemetry_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return TELEMETRY_FILE

def load_telemetry_records() -> List[Dict[str, Any]]:
    """Loads all historical token telemetry records from disk."""
    path = get_telemetry_path()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Error loading telemetry records: {e}")
        return []

def save_telemetry_records(records: List[Dict[str, Any]]):
    """Saves telemetry records to disk atomically."""
    path = get_telemetry_path()
    try:
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        temp_path.replace(path)
    except Exception as e:
        logger.error(f"Error saving telemetry records: {e}")

def record_token_usage(
    session_id: str,
    repo: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    thinking_tokens: int = 0,
    cache_read_tokens: int = 0,
    total_tokens: int = 0,
    timestamp: Optional[str] = None
) -> Dict[str, Any]:
    """Appends or updates a token usage record for a session."""
    if total_tokens <= 0 and (input_tokens + output_tokens + thinking_tokens) > 0:
        total_tokens = input_tokens + output_tokens + thinking_tokens

    ts = timestamp or datetime.now(timezone.utc).isoformat()
    record = {
        "session_id": session_id,
        "repo": repo or "unknown",
        "model": model or "unknown",
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "thinking_tokens": int(thinking_tokens),
        "cache_read_tokens": int(cache_read_tokens),
        "total_tokens": int(total_tokens),
        "timestamp": ts
    }

    records = load_telemetry_records()
    # Update existing record for session if same day or append new
    updated = False
    for i, r in enumerate(records):
        if r.get("session_id") == session_id:
            # Update with max observed values to avoid double counting
            records[i]["total_tokens"] = max(records[i].get("total_tokens", 0), int(total_tokens))
            records[i]["input_tokens"] = max(records[i].get("input_tokens", 0), int(input_tokens))
            records[i]["output_tokens"] = max(records[i].get("output_tokens", 0), int(output_tokens))
            records[i]["thinking_tokens"] = max(records[i].get("thinking_tokens", 0), int(thinking_tokens))
            records[i]["timestamp"] = ts
            updated = True
            break
    if not updated:
        records.append(record)

    save_telemetry_records(records)
    return record

def _parse_ts(ts_str: Optional[str]) -> Optional[datetime]:
    if not ts_str:
        return None
    try:
        # Handle trailing Z or timezone offsets
        clean = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def get_timescale_metrics(reference_time: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Computes token usage aggregated over multiple timescales:
    1 hour, 24 hours, 7 days, 30 days, and all-time,
    including hourly and daily trends, and breakdowns by model and repository.
    """
    now = reference_time or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    records = load_telemetry_records()

    # Time boundaries
    t_1h = now - timedelta(hours=1)
    t_24h = now - timedelta(hours=24)
    t_7d = now - timedelta(days=7)
    t_30d = now - timedelta(days=30)

    summary = {
        "last_1h_tokens": 0,
        "last_24h_tokens": 0,
        "last_7d_tokens": 0,
        "last_30d_tokens": 0,
        "all_time_tokens": 0,
        "all_time_cache_read_tokens": 0,
        "total_sessions_tracked": len(records)
    }

    hourly_buckets: Dict[str, Dict[str, int]] = {}
    # Pre-populate last 24 hours
    for h in range(23, -1, -1):
        dt_bucket = (now - timedelta(hours=h)).strftime("%Y-%m-%d %H:00")
        hourly_buckets[dt_bucket] = {"tokens": 0, "input": 0, "output": 0, "thinking": 0}

    daily_buckets: Dict[str, Dict[str, int]] = {}
    # Pre-populate last 30 days
    for d in range(29, -1, -1):
        d_bucket = (now - timedelta(days=d)).strftime("%Y-%m-%d")
        daily_buckets[d_bucket] = {"tokens": 0, "sessions": 0}

    by_model: Dict[str, int] = {}
    by_repo: Dict[str, int] = {}

    for r in records:
        toks = r.get("total_tokens", 0)
        inp = r.get("input_tokens", 0)
        out = r.get("output_tokens", 0)
        thk = r.get("thinking_tokens", 0)
        model = r.get("model", "unknown")
        repo = r.get("repo", "unknown")

        summary["all_time_tokens"] += toks
        summary["all_time_cache_read_tokens"] += r.get("cache_read_tokens", 0)
        by_model[model] = by_model.get(model, 0) + toks
        by_repo[repo] = by_repo.get(repo, 0) + toks

        dt = _parse_ts(r.get("timestamp"))
        if dt:
            if dt >= t_1h:
                summary["last_1h_tokens"] += toks
            if dt >= t_24h:
                summary["last_24h_tokens"] += toks
                h_key = dt.strftime("%Y-%m-%d %H:00")
                if h_key in hourly_buckets:
                    hourly_buckets[h_key]["tokens"] += toks
                    hourly_buckets[h_key]["input"] += inp
                    hourly_buckets[h_key]["output"] += out
                    hourly_buckets[h_key]["thinking"] += thk
            if dt >= t_7d:
                summary["last_7d_tokens"] += toks
            if dt >= t_30d:
                summary["last_30d_tokens"] += toks
                d_key = dt.strftime("%Y-%m-%d")
                if d_key in daily_buckets:
                    daily_buckets[d_key]["tokens"] += toks
                    daily_buckets[d_key]["sessions"] += 1

    # Format trends for API response
    hourly_trend = [{"hour": k, **v} for k, v in hourly_buckets.items()]
    daily_trend = [{"date": k, **v} for k, v in daily_buckets.items()]

    # Format model percentages
    all_toks = max(summary["all_time_tokens"], 1)
    model_breakdown = [
        {"model": m, "tokens": t, "percentage": round((t / all_toks) * 100, 1)}
        for m, t in sorted(by_model.items(), key=lambda x: x[1], reverse=True)
    ]
    repo_breakdown = [
        {"repo": r, "tokens": t, "percentage": round((t / all_toks) * 100, 1)}
        for r, t in sorted(by_repo.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "generated_at": now.isoformat(),
        "summary": summary,
        "hourly_trend": hourly_trend,
        "daily_trend": daily_trend,
        "model_breakdown": model_breakdown,
        "repo_breakdown": repo_breakdown,
        "by_model": model_breakdown,
        "by_repo": repo_breakdown
    }

def sync_from_sessions_cache(sessions_data: Any) -> int:
    """Syncs existing cached sessions from memory or data/sessions.json into telemetry."""
    count = 0
    for s in sessions_data:
        def get_val(key: str, default: Any = None):
            if isinstance(s, dict):
                return s.get(key, default)
            return getattr(s, key, default)

        sid = get_val("id") or get_val("session_id")
        if not sid:
            continue
        toks = get_val("total_tokens") or get_val("token_count") or 0
        if toks > 0:
            record_token_usage(
                session_id=str(sid),
                repo=get_val("repo", "BowenMichael/f1-frontend"),
                model=get_val("model", "gemini-3.8-flash"),
                input_tokens=get_val("input_tokens", 0) or 0,
                output_tokens=get_val("output_tokens", 0) or 0,
                thinking_tokens=get_val("thinking_tokens", 0) or 0,
                cache_read_tokens=get_val("cache_read_tokens", 0) or 0,
                total_tokens=int(toks),
                timestamp=get_val("last_activity_at") or get_val("updated_at") or get_val("created_at") or get_val("started_at")
            )
            count += 1
    return count
