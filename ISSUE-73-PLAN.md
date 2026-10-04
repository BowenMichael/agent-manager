# Implementation Plan: Decoupled Background Agents (Issue #73)

## 1. Architectural Overview

**Objective:**
Decouple agent execution processes from the FastAPI server lifecycle. Ensure that restarting, updating, or crashing the web server does not kill active agent runs, and that the server can seamlessly reconnect and resume streaming logs for active agents upon startup.

**Key Design Decisions:**
1. **Detached Worker Process:** Instead of coupling agents as child processes via `asyncio.create_subprocess_exec`, the system will spawn the `agy` CLI using `subprocess.Popen` with OS-level process isolation flags (`creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS` on Windows, `start_new_session=True` on Unix).
2. **Background Wrapper Script (`daemon_worker.py`):** Because detached processes break standard I/O pipes (and don't seamlessly report their exit codes back to a restarted parent), a tiny Python wrapper script will be introduced. The FastAPI server spawns this wrapper detached; the wrapper runs the `agy` command synchronously, redirects output to a JSONL log file, and writes the final return code to a `.exitcode` file upon completion.
3. **Log Tailing & Reattachment:** The web server will interact with the agent strictly by reading ("tailing") its output log file asynchronously. `AgentSessionInfo` will persist the `pid` and the `stream_log_offset` (how many bytes have been read). When the server restarts, `AgentRunnerManager._init_manager` will inspect all `RUNNING` sessions. If the process is alive (via `psutil`) or the log file has unread bytes, it will spawn a background task to resume tailing exactly where it left off, successfully recovering state.
4. **Process Lifecycle Management:** Operations like `stop_agent` or Circuit Breaker pauses will transition from using in-memory `proc.terminate()` to `psutil.Process(pid).terminate()` for cross-platform robustness.

---

## 2. Target Files & Modular Breakdown

*Note: Adhere strictly to the Anti-Monolith Rule (all files must be < 250 lines). Extract logic into the proposed new modular files.*

### A. Core Models & Configuration
- **`agent_manager/models.py`**
  - Update `AgentSessionInfo` to include:
    - `pid: Optional[int] = None`
    - `stream_log_file: Optional[str] = None`
    - `exit_code_file: Optional[str] = None`
    - `stream_log_offset: int = 0`

### B. New Modular Services
- **`agent_manager/runners/daemon_worker.py`** (New File)
  - A lightweight script executed via `sys.executable`.
  - Takes an exit code file path as `sys.argv[1]` and the `agy` CLI command array as `sys.argv[2:]`.
  - Runs the command (e.g., via `subprocess.run`), then writes the `returncode` to the exit code file before exiting.
- **`agent_manager/runners/process_manager.py`** (New File)
  - `launch_detached_agent(cmd: List[str], cwd: str, log_file: str, exit_file: str) -> int`: Wraps the `cmd` inside the `daemon_worker.py` execution. Opens `log_file` for write, and uses `subprocess.Popen(..., stdout=f, stderr=subprocess.STDOUT, creationflags=...)`. Returns the PID.
  - `is_process_alive(pid: int) -> bool`: Safe check using `psutil.Process(pid).is_running()`.
  - `terminate_process(pid: int)`: Gracefully terminates the process tree using `psutil`.
- **`agent_manager/runners/stream_tailer.py`** (New File)
  - Contains the async tailing loop extracted from `orchestrator.py`.
  - `tail_agent_log(manager, session_id: str)`: Opens `session.stream_log_file` at `session.stream_log_offset`. Reads lines sequentially, parses JSON, delegates to `handle_tool_call_stream`, updates `stream_log_offset`, and persists state. If EOF, checks `is_process_alive()`; if dead, reads `.exitcode` and triggers `handle_post_process`.

### C. Existing Logic Refactors
- **`agent_manager/runners/orchestrator.py`**
  - Refactor `run_agent_loop`: Remove `asyncio.create_subprocess_exec`. Generate paths for `logs/{session_id}.stream.jsonl` and `.exitcode`. Launch via `launch_detached_agent()`. Save `pid` to the session, and launch `tail_agent_log` as an asyncio task (tracked in `manager._tasks`).
- **`agent_manager/runners/stream_handler.py`**
  - Modify `handle_tool_call_stream` to accept `pid` instead of `proc`, utilizing `terminate_process(session.pid)` for circuit breaker halts.
- **`agent_manager/runners/lifecycle.py`**
  - Update `stop_agent` to utilize `terminate_process(session.pid)` instead of `proc.terminate()`.
- **`agent_manager/runner.py`**
  - Update `_init_manager`: After loading sessions, iterate over them. If `status == AgentStatus.RUNNING` and `pid` is set, invoke `tail_agent_log` as a background task to reattach and resume streaming.

---

## 3. Step-by-Step Implementation Guide

**Stage 1: Process Management & Worker Scripts**
1. Update `AgentSessionInfo` in `agent_manager/models.py` with the new tracking properties.
2. Create `agent_manager/runners/daemon_worker.py`. Keep it minimal (no external dependencies, just `sys`, `subprocess`, `json`).
3. Create `agent_manager/runners/process_manager.py`. Import `psutil`. Implement robust `launch_detached_agent`, `is_process_alive`, and `terminate_process` functions. Ensure correct Windows flags (`subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS`).

**Stage 2: Stream Tailing Module**
1. Create `agent_manager/runners/stream_tailer.py`.
2. Move the `while True:` JSON parsing loop out of `orchestrator.py` into `tail_agent_log`.
3. Implement file offset tracking: `f.seek(session.stream_log_offset)`. After a successful `readline()`, update `session.stream_log_offset = f.tell()`.
4. Ensure the tailer sleeps briefly (`await asyncio.sleep(0.1)`) if no line is read but the process is still alive, preventing CPU spinning.

**Stage 3: Integration & Reattachment**
1. Update `orchestrator.py` to use `launch_detached_agent` and schedule the `tail_agent_log` task.
2. Refactor `handle_tool_call_stream` (in `stream_handler.py`) and `stop_agent` (in `lifecycle.py`) to drop the `proc` object requirement and use `terminate_process(pid)` instead.
3. In `agent_manager/runner.py`'s `_init_manager`, write the reattachment logic that resurrects `tail_agent_log` tasks for `RUNNING` sessions with active PIDs on server reboot.

---

## 4. Verification & Testing Criteria

**Behavior to Verify:**
- **Execution Initiation:** When spawning an agent, a detached background process is successfully created. A log file and exit code file are generated.
- **Log Streaming:** The web application successfully tails the JSONL stream, accurately reporting tool executions, token counts, and broadcasting to WebSockets.
- **Server Restart Resilience:** While an agent is actively running (e.g., executing a slow command), killing the FastAPI web server process (CTRL+C) does NOT kill the agent process. Restarting the web server automatically discovers the running agent, resumes tailing the log from the exact byte offset, and broadcasts the completion/results to the UI.
- **Termination Correctness:** Triggering a "Stop" command from the UI successfully kills the detached process tree and cleans up.

**Test Commands / Log Validation (Command Log Suppression Active):**
1. Run backend tests to verify logic (redirect output!):
   ```powershell
   npm run test > test_run.log 2>&1
   ```
2. On failure, tail strictly 40 lines:
   ```powershell
   Get-Content -Tail 40 test_run.log
   ```
3. Always clean up logs `Remove-Item test_run.log -ErrorAction SilentlyContinue`.
