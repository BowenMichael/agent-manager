"""
Process Manager for Detached Agent Execution.
Handles spawning detached daemon worker processes, checking status, and process termination across platforms.
"""
import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("agent_manager.runners.process_manager")


def launch_independent_agent_service(
    session_id: str,
    cwd: str,
    log_file: str,
    exit_file: str,
    is_continuation: bool = False,
    prompt: Optional[str] = None
) -> int:
    """
    Spawns an agent as an independent daemon service process.
    The service runs detached and survives web server restarts and reloads.
    """
    service_script = Path(__file__).parent / "agent_service.py"
    full_cmd = [sys.executable, str(service_script), "--session-id", session_id]
    if is_continuation:
        full_cmd.append("--continue")
    if prompt:
        full_cmd.extend(["--prompt", prompt])

    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    Path(exit_file).parent.mkdir(parents=True, exist_ok=True)

    service_log = Path(cwd) / ".agent_logs" / f"{session_id}.service.log"
    log_handle = open(service_log, "a", encoding="utf-8", buffering=1)

    creationflags = 0
    start_new_session = False

    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        if hasattr(subprocess, "DETACHED_PROCESS"):
            creationflags |= subprocess.DETACHED_PROCESS
    else:
        start_new_session = True

    try:
        proc = subprocess.Popen(
            full_cmd,
            cwd=str(cwd),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            start_new_session=start_new_session,
            close_fds=(os.name != "nt")
        )
        return proc.pid
    finally:
        log_handle.close()


def launch_detached_agent(cmd: List[str], cwd: str, log_file: str, exit_file: str) -> int:
    """
    Spawns a detached process running daemon_worker.py, which executes the agent CLI.
    Stdout and stderr are redirected to log_file.
    Returns the PID of the spawned worker process.
    """
    worker_script = Path(__file__).parent / "daemon_worker.py"
    full_cmd = [sys.executable, str(worker_script), exit_file] + cmd

    # Ensure parent log directories exist
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    Path(exit_file).parent.mkdir(parents=True, exist_ok=True)

    log_handle = open(log_file, "a", encoding="utf-8", buffering=1)

    creationflags = 0
    start_new_session = False

    if os.name == "nt":
        # Windows: CREATE_NEW_PROCESS_GROUP (0x200) and DETACHED_PROCESS (0x8)
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        if hasattr(subprocess, "DETACHED_PROCESS"):
            creationflags |= subprocess.DETACHED_PROCESS
    else:
        # POSIX: start new session to detach from controlling terminal/parent process group
        start_new_session = True

    try:
        proc = subprocess.Popen(
            full_cmd,
            cwd=str(cwd),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            start_new_session=start_new_session,
            close_fds=(os.name != "nt")
        )
        return proc.pid
    finally:
        log_handle.close()


def is_process_alive(pid: Optional[int]) -> bool:
    """Checks if a process with given PID is currently active."""
    if not pid or pid <= 0:
        return False

    if os.name == "nt":
        try:
            # Query tasklist for PID to reliably verify existence on Windows without external dependencies
            res = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False
            )
            out = res.stdout.strip()
            return bool(out and f'"{pid}"' in out)
        except Exception as e:
            logger.debug(f"Error checking Windows PID {pid}: {e}")
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def terminate_process(pid: Optional[int]) -> bool:
    """Gracefully terminates a process and its children by PID."""
    if not pid or pid <= 0:
        return False

    if not is_process_alive(pid):
        return True

    if os.name == "nt":
        try:
            # /F force, /T tree kill
            res = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0:
                return True
            return not is_process_alive(pid)
        except Exception as e:
            logger.warning(f"Error terminating Windows PID {pid}: {e}")
            return not is_process_alive(pid)
    else:
        try:
            import signal
            try:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGTERM)
            except Exception:
                os.kill(pid, signal.SIGTERM)
            return True
        except OSError as e:
            logger.warning(f"Error terminating POSIX PID {pid}: {e}")
            return not is_process_alive(pid)
