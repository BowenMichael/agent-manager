# Implementation Plan: GitHub Issue #17
**Title**: [BACKEND]: Abstract Filesystem & Decouple Local Windows Path Dependencies

## 1. Architectural Overview
The goal is to decouple the backend from local Windows-specific environments, allowing the application to run seamlessly on both Windows development machines and headless Linux containers.

**Key Architectural Decisions**:
- **Path Abstraction**: Core configuration paths (`WORKSPACE_BASE`, `AGY_CLI_PATH`, `ANTIGRAVITY_IDE_CLI`, `CLI_SETTINGS_PATH`) will dynamically resolve OS-specific defaults using `sys.platform`. On POSIX systems, `WORKSPACE_BASE` will default to `/app/workspaces` and executables to `/usr/local/bin` or standard Linux locations. 
- **Cross-Platform Terminal Execution**: Spawning interactive terminal windows (`powershell -NoExit`) is strictly a Windows desktop feature. We will implement OS gates to intercept these requests on non-Windows platforms, falling back gracefully to headless (`web_stream`) mode.
- **Missing Binary Fallback**: In minimal container environments where the `agy` binary may be absent, attempting to spawn it via a detached subprocess leads to crash loops. A pre-flight existence check will be implemented to gracefully catch missing binaries and inject a simulated error response directly into the log stream.

## 2. Target Files & Modular Breakdown
*Sticking strictly to the anti-monolith guidelines, all modifications will be contained within their respective domain files, none of which exceed 250 LOC.*

- **`agent_manager/config.py`**: Update initialization logic for constants involving paths to conditionally check `sys.platform == "win32"`.
- **`agent_manager/runners/terminal_launcher.py`**: Add an OS-gate guard clause inside `launch_desktop_terminal`.
- **`agent_manager/runners/orchestrator.py`**: Enhance `run_agent_loop` to handle terminal launcher fallbacks and implement the pre-flight binary existence check.
- **`agent_manager/api/routes/agents.py`**: Add an OS-gate to the `/launch-terminal` (or similar) endpoint to prevent unsupported execution on Linux.

## 3. Step-by-Step Implementation Guide

**Step 1: Path & OS Abstraction (`config.py`)**
- Import the `sys` module.
- Modify `WORKSPACE_BASE` initialization: If `sys.platform == "win32"`, default to `e:/~Michael Bowen/Projects`; else default to `/app/workspaces`.
- Modify `AGY_CLI_PATH` and `ANTIGRAVITY_IDE_CLI`: Use `LOCALAPPDATA` paths for Windows, and `/usr/local/bin/agy` (or `agy` from `PATH`) for Linux.
- Modify `CLI_SETTINGS_PATH`: Ensure it falls back safely without assuming Windows directory structures.

**Step 2: Gate API Routes (`agent_manager/api/routes/agents.py`)**
- Locate the API route responsible for launching external terminals (e.g., generating the `powershell -NoExit` command).
- Insert a check: `if sys.platform != "win32": raise HTTPException(status_code=400, detail="Interactive terminal is only supported on Windows.")`

**Step 3: Refactor Terminal Launcher (`terminal_launcher.py`)**
- In the `launch_desktop_terminal` function, insert a guard clause at the start:
  - If `sys.platform != "win32"`, append a system message indicating the OS mismatch and return `False`.
- Update the signature or return type to indicate whether the terminal launch was successful so the caller can fall back.

**Step 4: Pre-flight Binary Checks & Fallbacks (`orchestrator.py`)**
- In `run_agent_loop`, handle the return value of `launch_desktop_terminal`. If it returns `False`, proceed to execute the standard headless `web_stream` flow.
- **Crucial Fallback**: Right before calling `launch_detached_agent`, check if `AGY_CLI_PATH.exists()`.
  - If it does **not** exist:
    - Avoid spawning the process.
    - Write a mock JSON error message (matching `stream-json` format) into the `log_file`.
    - Write a `1` into the `exit_code_file`.
    - Call `tail_agent_log` as usual so the UI streams the graceful error instead of crashing.

## 4. Verification & Testing Criteria

- **Unit Test Execution**:
  - Run the test suite on Windows to ensure no regressions:
    ```powershell
    pytest > test_run.log 2>&1
    Remove-Item test_run.log -ErrorAction SilentlyContinue
    ```
- **OS Mock Verification**:
  - Temporarily mock `sys.platform = "linux"` in `config.py` and verify that `WORKSPACE_BASE` resolves to `/app/workspaces`.
  - Verify that attempting to launch an agent in `terminal` mode under the mocked Linux OS falls back to `web_stream` mode automatically and bypasses PowerShell.
- **Missing Binary Resilience**:
  - Temporarily rename the `agy.exe` binary on the disk.
  - Trigger an agent session in `web_stream` mode.
  - **Expected Result**: The UI should display a clean error indicating the binary is missing, rather than experiencing a backend crash or infinite loop.
