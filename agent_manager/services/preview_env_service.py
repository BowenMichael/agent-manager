"""
Ephemeral Preview Environment Service.
Manages ephemeral local web servers and preview containers for active worktrees,
dynamic port allocation, HTTP readiness verification, and 10-minute timeout enforcement.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import logging
import os
import socket
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional, List, Any
import httpx

from agent_manager.runners.process_manager import is_process_alive, terminate_process

logger = logging.getLogger("agent_manager.services.preview_env")

MAX_PREVIEW_LIFETIME_SECONDS = 600  # 10 minute timeout guardrail


@dataclass
class PreviewInstance:
    session_id: str
    worktree_path: str
    port: int
    pid: int
    url: str
    started_at: float
    status: str  # "STARTING", "READY", "FAILED", "STOPPED"


_ACTIVE_PREVIEWS: Dict[str, PreviewInstance] = {}


def find_free_port() -> int:
    """Finds an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        return s.getsockname()[1]


def wait_for_ready(url: str, timeout_seconds: float = 10.0) -> bool:
    """Polls preview URL until HTTP 200/300 is returned or timeout expires."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with httpx.Client(timeout=1.0) as client:
                res = client.get(url)
                if res.status_code in (200, 301, 302, 304, 404):
                    return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def launch_preview_server(session_id: str, worktree_path: Path, port: Optional[int] = None) -> PreviewInstance:
    """Launches an ephemeral web server process inside the worktree directory."""
    reap_stale_previews()
    assigned_port = port or find_free_port()
    preview_url = f"http://127.0.0.1:{assigned_port}"

    cmd = ["python", "-m", "http.server", str(assigned_port), "--bind", "127.0.0.1"]
    dist_dir = worktree_path / "frontend" / "dist"
    cwd = dist_dir if dist_dir.is_dir() else worktree_path

    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    instance = PreviewInstance(
        session_id=session_id,
        worktree_path=str(worktree_path),
        port=assigned_port,
        pid=proc.pid,
        url=preview_url,
        started_at=time.time(),
        status="STARTING"
    )
    _ACTIVE_PREVIEWS[session_id] = instance

    is_ready = wait_for_ready(preview_url, timeout_seconds=8.0)
    instance.status = "READY" if is_ready else "FAILED"
    logger.info(f"Ephemeral preview for {session_id} launched at {preview_url} (PID: {proc.pid}, Status: {instance.status})")
    return instance


def stop_preview_server(session_id: str) -> bool:
    """Terminates an active preview server process tree and removes it from registry."""
    instance = _ACTIVE_PREVIEWS.pop(session_id, None)
    if not instance:
        return False

    if instance.pid and is_process_alive(instance.pid):
        terminate_process(instance.pid)
        logger.info(f"Terminated preview server for {session_id} (PID: {instance.pid})")
    instance.status = "STOPPED"
    return True


def reap_stale_previews() -> int:
    """Terminates any preview instances running longer than 10 minutes."""
    now = time.time()
    reaped = 0
    stale_ids = [
        sid for sid, p in _ACTIVE_PREVIEWS.items()
        if (now - p.started_at) > MAX_PREVIEW_LIFETIME_SECONDS or not is_process_alive(p.pid)
    ]
    for sid in stale_ids:
        stop_preview_server(sid)
        reaped += 1
    return reaped


def list_active_previews() -> List[Dict[str, Any]]:
    """Returns serialized active preview environments."""
    reap_stale_previews()
    return [asdict(p) for p in _ACTIVE_PREVIEWS.values()]
