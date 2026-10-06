# Architecture Report & Migration Plan: Async Agent Execution (Issue #84)

## 1. Architectural Overview

### Current Bottlenecks & Synchronous Constraints
The current architecture in `agent_manager` executes agents by spawning a detached process via `subprocess.Popen` (in `process_manager.py`) and then relies on `stream_tailer.py` to tail a local JSONL log file. 
- **Blocking I/O:** `stream_tailer.py` uses a synchronous file open and `f.readline()` in a `while True` loop inside an asynchronous task. This blocks the main thread's event loop, preventing FastAPI from efficiently handling concurrent HTTP requests and WebSocket pings.
- **Fragile Process Tracking:** Lifecycle management relies on OS-specific PID polling (`tasklist` on Windows, `os.kill` on POSIX), which is brittle and prevents horizontal scaling.
- **Tight Coupling:** The API server and the agent runners are tightly coupled by local disk storage (`.agent_logs`), making containerization or distributed execution impossible.

### Target Architecture
To unblock the core server, we will migrate to a **Webhook/Callback-Driven Worker Architecture** powered by a lightweight task queue (like `arq` or python's `asyncio` combined with internal HTTP callbacks).
1. **Server as Event Receiver:** The server will no longer monitor processes or read files. It will expose an internal API (`/api/internal/worker/...`) to receive state updates.
2. **Agent as Independent Worker:** Agents will be dispatched as independent background tasks. They will execute the Antigravity CLI and pipe their output directly to the server's internal webhook, rather than writing to disk.
3. **Decoupled Lifecycle:** Session states (RUNNING, PAUSED, COMPLETED) will be updated dynamically via these callbacks.

---

## 2. Target Files & Modular Breakdown

STRICT ANTI-MONOLITH RULE APPLIED: No files over 250 lines. Components are decomposed by responsibility.

### Files to Deprecate / Delete
- `agent_manager/runners/stream_tailer.py` (Delete - removes synchronous file I/O).
- `agent_manager/runners/process_manager.py` (Delete - removes brittle PID tracking).

### Files to Create (New Modules)
- `agent_manager/api/routes/worker_callbacks.py` (< 150 lines): New FastAPI router to receive progress updates, token usage, and status changes directly from the background agent.
- `agent_manager/jobs/dispatcher.py` (< 100 lines): Handles submitting the agent task to the background worker pool (using `asyncio.subprocess` or a lightweight queue).
- `agent_manager/jobs/worker.py` (< 200 lines): The standalone script that executes the Antigravity CLI and pushes JSON stream updates to the `worker_callbacks` HTTP endpoint.

### Files to Modify
- `agent_manager/server.py`: Register the new `worker_callbacks` router.
- `agent_manager/runners/orchestrator.py`: Refactor `run_agent_loop` to use `agent_manager.jobs.dispatcher` instead of local process spawning.
- `agent_manager/runner.py`: Remove `_reattach_active_sessions` PID-polling logic. Rely on workers reporting their own active state.

---

## 3. Step-by-Step Implementation Guide

**Step 1: Create the Worker Callback API (`agent_manager/api/routes/worker_callbacks.py`)**
- Implement a POST endpoint `/api/internal/worker/{session_id}/stream`.
- Implement a POST endpoint `/api/internal/worker/{session_id}/status`.
- These endpoints will receive the parsed JSON objects from the agent, update the `AgentSessionInfo`, and trigger `manager.broadcast()` to push updates to the UI via WebSockets.

**Step 2: Build the Background Worker (`agent_manager/jobs/worker.py`)**
- Create a standalone async Python script that receives the Antigravity CLI command.
- Use `asyncio.create_subprocess_exec` with `stdout=asyncio.subprocess.PIPE`.
- Asynchronously read `stdout.readline()`, and immediately send the parsed JSON payload to the server's `/api/internal/worker/{session_id}/stream` endpoint via `httpx.AsyncClient`.
- Send a final status update (success/fail) to the `/status` endpoint when the process exits.

**Step 3: Refactor Orchestrator & Dispatcher (`agent_manager/jobs/dispatcher.py`)**
- Extract the dispatch logic from `orchestrator.py`.
- Instead of calling `launch_detached_agent`, the dispatcher will spawn `agent_manager/jobs/worker.py` in the background (or submit it to a queue).
- Ensure the worker receives the server URL (e.g., `http://localhost:{PORT}`) to know where to send callbacks.

**Step 4: Cleanup & Remove Sync File Tailing**
- Delete `stream_tailer.py` and `process_manager.py`.
- Remove references to `log_file`, `exit_file`, and `pid` in `AgentSessionInfo` and `runner.py`.

---

## 4. Verification & Testing Criteria

### Expected Behavior
- Agents start successfully without blocking the main event loop.
- The UI live-stream (WebSockets) continues to update smoothly without jitter.
- The server responds instantly to HTTP requests (e.g., ping) even while multiple agents are actively generating text.
- No `.agent_logs` files are written to disk.

### Test Commands & Log Suppression
1. **Type Checking:** Ensure the new modular files are strictly typed.
   ```powershell
   npx tsc --noEmit > tsc_run.log 2>&1
   ```
2. **Backend Unit Tests:** Run existing tests to ensure no regressions in orchestration.
   ```powershell
   python -m pytest tests/ > pytest_run.log 2>&1
   ```
3. **Inspect Failures (Only if non-zero exit code):**
   ```powershell
   Get-Content -Tail 40 pytest_run.log
   ```
4. **Cleanup:**
   ```powershell
   Remove-Item tsc_run.log, pytest_run.log -ErrorAction SilentlyContinue
   ```

### Verification Checklist
- [ ] Server event loop remains unblocked during agent execution.
- [ ] `stream_tailer.py` synchronous file reads are completely removed.
- [ ] Agent state and token updates are pushed via HTTP callbacks.
- [ ] No monolithic files > 250 lines created.
