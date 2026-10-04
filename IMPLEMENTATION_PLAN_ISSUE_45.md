# Implementation Plan for Issue #45: Refactor to make code less monolithic

## 1. Architectural Overview
The `agent-manager` codebase currently contains several monolithic components that violate the Anti-Monolith Directive (files > 300 LOC). The primary objective is to decompose these files into highly modular, single-responsibility components with clear boundaries. 
This refactor primarily affects:
- The Frontend Application (`app.js` -> `api`, `socket`, `ui/`)
- The Backend Process Runner (`runner.py` -> `runners/process_manager`, `stream_handler`, etc.)
- The Backend Services (`poller.py`, `cron_dispatcher.py`, `server.py` -> `api/routes/`)
- The Test Suite (`test_manager.py` -> isolated test domains)

**Key Design Decisions:**
- **Facade Pattern**: Existing import paths (e.g., `import runner`) will be preserved where possible by creating facade files or `__init__.py` module exports that aggregate the decomposed internals.
- **Dependency Injection**: Refactored submodules will receive shared states (e.g., configurations, websocket clients) as parameters rather than importing global mutable state.
- **Routing Modules**: FastAPI routes will be moved to an APIRouter-based blueprint structure in `agent_manager/api/routes/`.

## 2. Target Files & Modular Breakdown
*Note: All new files strictly adhere to the <250 LOC rule.*

### A. Frontend Refactoring (`agent_manager/static/app.js` - 1,658 LOC)
- **Create Directory**: `agent_manager/static/js/`
- **New Files**:
  - `agent_manager/static/js/api.js`: Fetch wrappers and backend API calls.
  - `agent_manager/static/js/socket.js`: Websocket connection management and event dispatching.
  - `agent_manager/static/js/ui/dashboard.js`: DOM manipulation for the main dashboard view.
  - `agent_manager/static/js/ui/modals.js`: Event listeners and state logic for modals/dialogs.
  - `agent_manager/static/js/app.js` (Entrypoint): Initializes submodules and acts as the orchestrator.
- **Modify**: Update `index.html` to import the new modular scripts (via ES modules `<script type="module">` or build system).

### B. Runner De-monolithing (`agent_manager/runner.py` - 1,392 LOC)
- **Create Directory**: `agent_manager/runners/`
- **New Files**:
  - `agent_manager/runners/process_manager.py`: Subprocess spawning and lifecycle management.
  - `agent_manager/runners/stream_handler.py`: Standard I/O redirection and logging.
  - `agent_manager/runners/worktree_manager.py`: Git worktree setup and teardown logic.
  - `agent_manager/runners/orchestrator.py`: High-level workflow orchestration combining the above components.
- **Modify**: `agent_manager/runner.py` becomes a facade/export module that simply imports and re-exports from `runners/` to preserve backward compatibility.

### C. Poller De-monolithing (`agent_manager/poller.py` - 389 LOC)
- **Create Directory**: `agent_manager/poller/`
- **New Files**:
  - `agent_manager/poller/github_client.py`: GitHub API interaction layer.
  - `agent_manager/poller/event_parser.py`: Webhook / polling payload parsing and validation.
  - `agent_manager/poller/synchronizer.py`: State synchronization between GitHub issues and local states.
- **Modify**: `agent_manager/poller.py` becomes a facade.

### D. Cron & Server Refactoring (`cron_dispatcher.py` & `server.py`)
- **New Files (Cron)**:
  - `agent_manager/cron/scheduler.py`: Abstract scheduling logic.
  - `agent_manager/cron/task_dispatcher.py`: Task execution mapping.
  - `agent_manager/cron_dispatcher.py` -> facade.
- **New Files (Server)**:
  - `agent_manager/api/routes/agents.py`: Agent lifecycle routes.
  - `agent_manager/api/routes/github.py`: Webhooks and GitHub board sync routes.
  - `agent_manager/api/routes/system.py`: Health checks and configuration routes.
  - `agent_manager/server.py`: FastAPI app initialization and router inclusion.

### E. Test Suite Split (`tests/test_manager.py` - 664 LOC)
- **Delete/Archive**: `tests/test_manager.py`
- **New Files**:
  - `tests/test_runner.py`: Tests for `agent_manager/runners/*`.
  - `tests/test_poller.py`: Tests for `agent_manager/poller/*`.
  - `tests/test_cron.py`: Tests for `agent_manager/cron/*`.
  - `tests/test_server.py`: Tests for API routes and FastAPI endpoints.

## 3. Step-by-Step Implementation Guide

**Step 1: Test Suite Baseline & Routing**
- Read and verify the existing test suite (`pytest > test_run.log 2>&1`).
- Break down `tests/test_manager.py` into the 4 target files.
- Run tests again to ensure exact same coverage/passing state.

**Step 2: Backend Refactoring (Runners & Cron)**
- Create `agent_manager/runners/` and `agent_manager/cron/` directories.
- Carefully extract classes and functions from `runner.py` and `cron_dispatcher.py` into their new target files.
- Refactor imports within the new files.
- Convert `runner.py` and `cron_dispatcher.py` into export facades.
- **Verification**: Run `pytest tests/test_runner.py tests/test_cron.py > test_run.log 2>&1` and inspect the log only on failure.

**Step 3: Backend Refactoring (Poller & Server)**
- Create `agent_manager/poller/` and `agent_manager/api/routes/`.
- Extract GitHub logic from `poller.py` into `poller/` submodules. Convert `poller.py` to a facade.
- Extract FastAPI endpoints from `server.py` into `api/routes/*.py`. Register them as APIRouters inside `server.py`.
- **Verification**: Run `pytest tests/test_poller.py tests/test_server.py > test_run.log 2>&1`.

**Step 4: Frontend Refactoring (app.js)**
- Create `agent_manager/static/js/` and subdirectories (`ui/`).
- Split `app.js` logic into `api.js`, `socket.js`, `ui/dashboard.js`, and `ui/modals.js`.
- Integrate them via ES modules in `app.js`.
- Update `index.html` to reference the new structure.

## 4. Verification & Testing Criteria
- **CLI/Command Logs**: All test commands must use output redirection (`> test_run.log 2>&1`). Inspect only via `Get-Content -Tail 40 test_run.log` on failure.
- **Backward Compatibility**: Modules importing `agent_manager.runner` or `agent_manager.poller` must not break.
- **LOC Constraints**: No new or refactored file may exceed 250 LOC. Check using `Get-Content <file> | Measure-Object -Line`.
- **End-to-End**: Ensure the FastAPI server can start up cleanly (`uvicorn agent_manager.server:app --reload > server.log 2>&1` in background, then curl healthcheck).
