# Architecture & Implementation Plan: Issue #65 (Detailed Telemetry Page)

## 1. Architectural Overview

**Goal:** Transform the existing telemetry popup modal into a comprehensive, standalone Telemetry Page. This page will display existing token timescale charts alongside new, detailed agent performance metrics and actionable optimization reports.

**Strategy:**
- **Frontend Refactoring:** We will extract the hardcoded `modal-telemetry` structure from `index.html` into a native web component `telemetry-view.js`. We will delete the modal from `index.html` and the associated `telemetry.js` module. A new navigation tab (button) in the top header will toggle this full-page view, joining `Projects View` and `Cron Runs`.
- **Backend Analytics Engine:** Because `agent_manager/telemetry.py` is nearing the strict 250-line monolith limit, we will create a dedicated `agent_manager/services/telemetry_service.py` to handle the generation of optimization reports and task performance analytics. It will process raw session data and return aggregated performance statistics.
- **API Extension:** We will add a new GET endpoint `/api/telemetry/reports` to the `system.py` router to serve the newly computed optimization reports to the frontend.

---

## 2. Target Files & Modular Breakdown

*Strict Anti-Monolith Directive: No file will exceed 250 lines.*

### New Files
1. **`agent_manager/services/telemetry_service.py`**
   - **Responsibility:** Pure analytics engine. Reads `AgentSessionInfo` objects via `storage.load_sessions()` to calculate task completion times, average turns, success/failure rates, and detect optimization anomalies (e.g., circuit breaker triggers).
2. **`agent_manager/static/components/telemetry-view.js`**
   - **Responsibility:** Native Web Component (`<telemetry-view>`). Replaces the old modal. Fetches and renders token data from `/api/telemetry/tokens` and performance reports from `/api/telemetry/reports`.
3. **`agent_manager/static/components/telemetry-view.css`**
   - **Responsibility:** Dedicated styles for the telemetry page.

### Files to Modify
4. **`agent_manager/api/routes/system.py`**
   - **Responsibility:** Add new `@router.get("/telemetry/reports")` calling `telemetry_service.py`.
5. **`agent_manager/static/index.html`**
   - **Responsibility:** Delete modal code, register new `<telemetry-view>` in the `console-panel`, and update header navigation buttons.
6. **`agent_manager/static/style.css`**
   - **Responsibility:** Remove old `.telemetry-*` modal styles (moved to `telemetry-view.css`).
7. **`agent_manager/static/modules/sessions.js` & `actions.js`**
   - **Responsibility:** Implement `showTelemetryView()` navigation logic (hiding other views, updating active header button states).

### Files to Delete
8. **`agent_manager/static/modules/telemetry.js`**
   - **Responsibility:** Obsolete. All logic moves to the `telemetry-view` component.

---

## 3. Step-by-Step Implementation Guide

### Phase 1: Backend Analytics & API
1. **Create `agent_manager/services/telemetry_service.py`**:
   - Implement `generate_optimization_reports()`.
   - Read all sessions via `from agent_manager.storage import load_sessions`.
   - Compute **Agent Performance Metrics**:
     - `avg_duration_seconds`
     - `avg_turns`
     - `success_rate_percent` (Completed vs. Failed/Circuit-breaker)
   - Compute **Optimization Alerts (Insights)**:
     - Identify sessions where `circuit_breaker_triggered == True`.
     - Identify sessions with high `consecutive_duplicate_tool_count`.
     - Output actionable recommendations for these flagged sessions (e.g., "Agent exceeded turn limit; consider breaking task into smaller sub-tasks.").
2. **Update `agent_manager/api/routes/system.py`**:
   - Add a new route `@router.get("/telemetry/reports")`.
   - Ensure it calls the new service and returns the aggregated JSON payload.

### Phase 2: Frontend Layout & CSS Refactoring
1. **Update `agent_manager/static/index.html`**:
   - **Header Nav**: Replace `<button id="btn-telemetry-modal">` with a link-pill style button `<button class="btn btn-secondary link-pill" id="btn-header-telemetry">Telemetry</button>` placed next to `btn-header-cron`.
   - **Main Panel**: Inside `<section class="console-panel" id="console-panel">`, add `<telemetry-view id="global-telemetry-view" class="hidden"></telemetry-view>`.
   - **Cleanup**: Delete the entire `<div class="modal-overlay hidden" id="modal-telemetry">` block. Remove `<script src="/static/modules/telemetry.js"></script>`. Add references to the new `telemetry-view.css` and `telemetry-view.js`.
2. **Extract CSS**:
   - Move `.telemetry-stats-grid`, `.telemetry-tabs`, `.telemetry-bar-col`, etc. from `style.css` to `agent_manager/static/components/telemetry-view.css`. Expand these styles to support a full-page layout and report cards.

### Phase 3: Telemetry View Component & Navigation
1. **Create `agent_manager/static/components/telemetry-view.js`**:
   - Define `class TelemetryView extends HTMLElement`.
   - In `connectedCallback`, fetch data from `/api/telemetry/tokens` and the new `/api/telemetry/reports`.
   - Render the timescale charts (porting logic from the old `telemetry.js`).
   - Render the new "Optimization Reports" section, iterating through the alerts to display session IDs, repos, reasons, and recommendations.
2. **Update Navigation (`sessions.js` / `actions.js`)**:
   - In `sessions.js`, add `window.showTelemetryView = function() { ... }`.
   - Hide `console-active`, `console-empty`, `global-dashboard`, `global-projects-view`, `global-cron-view`, and show `global-telemetry-view`.
   - Update `.active` classes on `btn-header-projects`, `btn-header-cron`, and `btn-header-telemetry`.
   - In `actions.js`, add event listeners to `#btn-header-telemetry` and `#stat-pill-tokens` to call `showTelemetryView()`.

### Phase 4: Final Cleanup
- `git rm agent_manager/static/modules/telemetry.js`.
- Ensure no residual modal click handlers exist.

---

## 4. Verification & Testing Criteria

### A. Execution Guardrails (Critical Rule Enforcement)
- All commands MUST suppress output via `> test_run.log 2>&1`. Only `Get-Content -Tail 40` on failure.

### B. Validation Checklist
1. **Codebase Structural Checks:**
   - Verify `telemetry.js` is deleted.
   - Verify `telemetry_service.py` is under 250 lines.
2. **API Verification:**
   - Command: `curl -s http://localhost:8000/api/telemetry/reports > api_test.log` (if server is running during test phase) or inspect FastAPI test client output.
   - Expectation: Returns a valid JSON with performance metrics and optimization alerts.
3. **Frontend Verification:**
   - Telemetry button in header correctly navigates to the full page view.
   - Both tokens and optimization insights render without JS console errors.
4. **Visual Proof:**
   - The implementation agent must capture a screenshot or UI demonstration of the full page in action as per the issue requirements.
