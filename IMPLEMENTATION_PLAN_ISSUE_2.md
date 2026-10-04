# Implementation Plan for Issue #2

## 1. Architectural Overview
**Root Cause Analysis:**
The intermittent failure stems from two interconnected issues across the backend and frontend:
1. **Frontend Flaw**: The client-side code in `agent_manager/static/app.js` frequently calls `await res.json()` *before* verifying `res.ok` or checking the `Content-Type` header. 
2. **Backend Unhandled Exceptions**: When the `/api/settings` endpoint encounters an unhandled exception (e.g., a file lock or concurrency issue on Windows), FastAPI's default global exception handler catches it. Without a custom handler, it can return a plain-text `500 Internal Server Error` response.
3. **The Crash**: Because the frontend blindly calls `res.json()` on the plain-text 500 response, the browser's JSON parser encounters the 'I' in "Internal Server Error", throwing a fatal `SyntaxError` (`Unexpected token 'I'`). This prevents the application's error-handling logic from surfacing a graceful toast notification.

**Design Strategy:**
- **Backend API Contract Guarantee**: We will wrap the settings persistence logic in a broad try-except block, explicitly raising an `HTTPException(status_code=500)`. This guarantees that even catastrophic failures return a well-formed JSON error response (`{"detail": "..."}`).
- **Frontend Safe Fetching**: We will implement a robust `safeFetch` or standard response validation pattern in `app.js` to ensure the application never attempts to parse non-JSON responses. We will systematically refactor the existing fetch calls to check `res.ok` and the `Content-Type` header prior to invocation.

## 2. Target Files & Modular Breakdown
- **`agent_manager/server.py`**:
  - Target: `@app.post("/api/settings")`
  - Action: Add a top-level `try...except Exception as e` wrapper to catch unhandled errors and raise structured `HTTPException`s.
- **`agent_manager/static/app.js`**:
  - Target: The `btnSaveSettings.addEventListener('click', ...)` fetch logic.
  - Target: Other fetch blocks making the same mistake (e.g., interrupt, stop, simulate endpoints).
  - Action: Implement response validation (`res.ok` and `Content-Type` checks) before `res.json()`.

## 3. Step-by-Step Implementation Guide
### Step 1: Backend Exception Handling
1. Open `agent_manager/server.py`.
2. Locate the `update_settings` asynchronous function.
3. Wrap the core logic (from extracting the environment file path down to the broadcast emission) in a `try` block.
4. Catch `Exception as e`, log it as an error using `logger.exception`, and raise a `fastapi.HTTPException` with `status_code=500` and a `detail` string containing the error message.

### Step 2: Frontend Safe Validation for Settings Save
1. Open `agent_manager/static/app.js`.
2. Locate the `fetch('/api/settings', ...)` block inside the save settings listener (around line 1200).
3. Update the logic to first check `!res.ok`. If false, safely read the error response (using `res.text()` or safely attempting to parse JSON if the content-type is `application/json`), and throw an `Error` with the parsed detail.
4. Only call `await res.json()` if the response is successful and valid.

### Step 3: Global Frontend Validation Audit
1. In `agent_manager/static/app.js`, search for other occurrences of `await res.json()` that happen *before* checking `res.ok`.
2. Examples include the endpoints for interrupting agents, resuming agents, and completing agents.
3. Refactor these instances to follow the same safe validation pattern, ensuring no other UI interactions can trigger the `Unexpected token` crash.

## 4. Verification & Testing Criteria
**Backend JSON Enforcement Validation:**
1. Temporarily inject a simulated failure (`raise Exception("Simulated Lock Error")`) inside `update_settings` in `server.py`.
2. Attempt to save settings from the UI.
3. Verify the frontend displays a red Toast notification reading `Failed to save settings: Simulated Lock Error` rather than crashing in the console.

**Normal Operation Validation:**
1. Remove the simulated failure.
2. Change a setting in the UI (e.g., switch the model) and click Save.
3. Verify the success toast appears and the settings persist correctly upon a page refresh.
4. Run tests with output suppressed to verify guardrails and pipeline settings remain unaffected:
   ```powershell
   pytest tests/test_manager.py > test_run.log 2>&1
   Remove-Item test_run.log -ErrorAction SilentlyContinue
   ```
