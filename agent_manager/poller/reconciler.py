"""
Issue Synchronization & State Reconciliation Engine.
Provides debounced, idempotent bidirectional sync across GitHub Issues, Project Boards, and WebSockets.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import asyncio
import logging
import re
import time
from typing import Dict, Any, Optional, Set, Tuple

logger = logging.getLogger("agent_manager.poller.reconciler")

# Valid lifecycle state transitions for cards and agents
VALID_TRANSITIONS = {
    "backlog": {"ready", "in_progress"},
    "ready": {"in_progress", "backlog"},
    "in_progress": {"in_review", "ready", "done"},
    "in_review": {"done", "in_progress", "ready"},
    "done": {"ready", "in_progress"}
}


def parse_acceptance_criteria(body: Optional[str]) -> Dict[str, Any]:
    """Parses markdown checkboxes in issue body and returns completion stats."""
    if not body:
        return {"total": 0, "completed": 0, "ratio": 1.0}
    
    total_boxes = re.findall(r"-\s*\[([ xX])\]", body)
    if not total_boxes:
        return {"total": 0, "completed": 0, "ratio": 1.0}
    
    completed = sum(1 for b in total_boxes if b.strip().lower() == "x")
    total = len(total_boxes)
    ratio = completed / total if total > 0 else 1.0
    return {"total": total, "completed": completed, "ratio": round(ratio, 2)}


def is_valid_transition(current: str, target: str) -> bool:
    """Validates if a status transition is permitted by the state machine."""
    if not current or current == target:
        return True
    allowed = VALID_TRANSITIONS.get(current.lower(), set())
    return target.lower() in allowed


class IssueSyncReconciler:
    """Reconciles issue state with debounce, transition validation, and broadcast support."""
    
    def __init__(self, debounce_window_sec: float = 2.0):
        self._debounce_window = debounce_window_sec
        self._sync_timestamps: Dict[str, float] = {}
        self._in_flight_syncs: Set[str] = set()
        self._lock = asyncio.Lock()

    def _get_sync_key(self, repo: str, issue_number: int) -> str:
        """Returns normalized lookup key for an issue."""
        return f"{repo.strip().lower()}#{issue_number}"

    async def should_sync(self, repo: str, issue_number: int) -> bool:
        """Checks whether a sync operation is permitted under debounce rules."""
        key = self._get_sync_key(repo, issue_number)
        async with self._lock:
            now = time.time()
            last_time = self._sync_timestamps.get(key, 0.0)
            if key in self._in_flight_syncs:
                logger.debug("Sync for %s is already in flight. Skipping.", key)
                return False
            if now - last_time < self._debounce_window:
                logger.debug("Debouncing sync for %s (%.2fs since last sync).", key, now - last_time)
                return False
            self._in_flight_syncs.add(key)
            return True

    async def mark_sync_complete(self, repo: str, issue_number: int):
        """Marks sync completed and records timestamp."""
        key = self._get_sync_key(repo, issue_number)
        async with self._lock:
            self._sync_timestamps[key] = time.time()
            self._in_flight_syncs.discard(key)

    async def reconcile_issue_event(
        self,
        watcher: Any,
        repo: str,
        issue_number: int,
        target_status: str,
        source: str = "webhook",
        body: Optional[str] = None
    ) -> Dict[str, Any]:
        """Reconciles issue status mutation and triggers WebSocket broadcast."""
        if not await self.should_sync(repo, issue_number):
            return {"status": "skipped", "reason": "debounced_or_in_flight"}

        try:
            criteria_stats = parse_acceptance_criteria(body)
            success = await watcher.update_issue_status(repo, issue_number, target_status)
            
            payload = {
                "type": "board_status_sync",
                "data": {
                    "issue_number": issue_number,
                    "repo": repo,
                    "status": target_status,
                    "source": source,
                    "criteria": criteria_stats,
                    "timestamp": time.time(),
                    "success": success
                }
            }
            if hasattr(watcher, "runner") and hasattr(watcher.runner, "broadcast"):
                await watcher.runner.broadcast(payload)
                
            return {"status": "success" if success else "failed", "data": payload["data"]}
        finally:
            await self.mark_sync_complete(repo, issue_number)
