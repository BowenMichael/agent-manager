"""
Metric History & Traceability Service.
Records immutable time-series snapshots of Manifesto metrics and Code Health,
computes historical trend deltas, and validates progression velocity.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger("agent_manager.services.metric_history")
MAX_HISTORY_ENTRIES = 500


def get_history_file_path() -> Path:
    """Returns absolute path to the manifesto history storage file."""
    repo_root = Path(__file__).resolve().parents[2]
    history_file = repo_root / "data" / "manifesto_history.json"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    return history_file


def _get_current_git_commit() -> str:
    """Retrieves short git commit SHA or placeholder."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=3
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "unknown"


def load_metric_history() -> List[Dict[str, Any]]:
    """Loads all historical metric snapshots from disk."""
    path = get_history_file_path()
    if not path.exists():
        return []
    try:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"Failed to load metric history: {e}")
        return []


def save_metric_history(records: List[Dict[str, Any]]) -> None:
    """Persists historical metric snapshots to disk."""
    path = get_history_file_path()
    try:
        path.write_text(json.dumps(records[-MAX_HISTORY_ENTRIES:], indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to save metric history: {e}")


def record_metric_snapshot(report: Dict[str, Any], git_commit: Optional[str] = None) -> Dict[str, Any]:
    """Records a single snapshot of the Manifesto compliance report."""
    history = load_metric_history()
    now_iso = datetime.now(timezone.utc).isoformat()
    sha = git_commit or _get_current_git_commit()

    pillar_scores = {k: v.get("score", 0.0) for k, v in report.get("pillars", {}).items()}
    snapshot = {
        "id": f"snapshot_{len(history) + 1}",
        "timestamp": now_iso,
        "git_commit": sha,
        "manifesto_health_index": report.get("manifesto_health_index", 0.0),
        "grade": report.get("grade", "GROUND_FLOOR"),
        "pillars": pillar_scores,
    }

    # Deduplicate rapid consecutive identical snapshots
    if history:
        last = history[-1]
        if last.get("git_commit") == sha and last.get("manifesto_health_index") == snapshot["manifesto_health_index"]:
            return last

    history.append(snapshot)
    save_metric_history(history)
    return snapshot


def compute_metric_trends() -> Dict[str, Any]:
    """Calculates historical trajectory deltas, velocity, and trend direction."""
    history = load_metric_history()
    if not history:
        return {
            "status": "NO_HISTORY",
            "total_snapshots": 0,
            "overall_delta": 0.0,
            "direction": "stable",
        }

    first = history[0]
    latest = history[-1]
    baseline_score = first.get("manifesto_health_index", 0.0)
    current_score = latest.get("manifesto_health_index", 0.0)
    overall_delta = round(current_score - baseline_score, 1)

    direction = "improving" if overall_delta > 0 else ("declining" if overall_delta < 0 else "stable")
    pillar_deltas = {}
    for p_name, cur_val in latest.get("pillars", {}).items():
        base_val = first.get("pillars", {}).get(p_name, 0.0)
        pillar_deltas[p_name] = round(cur_val - base_val, 1)

    return {
        "status": "TRACKED",
        "total_snapshots": len(history),
        "baseline_score": baseline_score,
        "current_score": current_score,
        "overall_delta": overall_delta,
        "direction": direction,
        "first_recorded": first.get("timestamp"),
        "last_recorded": latest.get("timestamp"),
        "pillar_deltas": pillar_deltas,
        "snapshots": history[-30:],
    }
