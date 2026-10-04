# Implementation Plan: GitHub Issue #32 (Agent Summary Dashboard)

## 1. Architectural Overview

**Objective**: Provide a real-time, automatically refreshing dashboard view summarizing the activity and operational state of all active agent sessions. 

**Approach**:
1. **Frontend Decomposition**: Instead of injecting more logic into `app.js` or `index.html`, we will create a dedicated web component (`<agent-summary-overview>`) responsible for rendering a grid of agent summary cards.
2. **Data Flow**: The backend already broadcasts state changes via WebSocket (`session_updated`, `init`, etc.). The existing `app.js` will intercept these messages and pass the updated `sessions` array directly to the new `<agent-summary-overview>` component. The component will reactively re-render the cards.
3. **UI Integration**: We will introduce a "Dashboard View" state. When no specific agent is selected (or when the user clicks a new "Overview / Dashboard" button in the sidebar), the dashboard component is shown in the main console panel. Clicking on an individual card will trigger `selectSession(id)` to switch to the detailed view.
4. **Backend Contract**: The existing `/api/agents` endpoint and `AgentSessionInfo` model provide the required fields (`current_activity`, `status`, `workflow_stage`, `turn_count`, `quota_percent`, `is_stalled`). We will add specific unit tests to enforce this data contract.

---

## 2. Target Files & Modular Breakdown

*Strict Anti-Monolith Rule: All new files must remain well under 250 lines.*

**Frontend Components**:
- **CREATE**: `agent_manager/static/components/agent-summary-overview.js`
  - Defines `AgentSummaryOverview` (container/grid) and `AgentSummaryCard` (individual row/card) Web Components.
  - Implements a `set sessions(data)` setter that updates the DOM efficiently.
  - Dispatches events when a card is clicked to trigger navigation.
- **CREATE**: `agent_manager/static/components/agent-summary-overview.css`
  - Styles for the dashboard layout, status badges, progress bars, and real-time activity text.

**Frontend Integration**:
- **MODIFY**: `agent_manager/static/index.html`
  - Add `<link>` for the new CSS and `<script>` for the new JS component.
  - Add a "Dashboard Overview" button in the sidebar (above the session list).
  - Add `<agent-summary-overview id="global-dashboard" class="hidden"></agent-summary-overview>` alongside `console-empty` and `console-active`.
- **MODIFY**: `agent_manager/static/app.js`
  - Add logic to toggle visibility between `console-active`, `console-empty`, and `global-dashboard`.
  - Update `handleWsMessage` and `renderSessionsList` to push the `sessions` array to `document.getElementById('global-dashboard').sessions = sessions`.
  - Wire the "Dashboard Overview" button to set `activeSessionId = null` and show the dashboard.

**Backend Testing**:
- **CREATE**: `tests/test_agent_summary.py`
  - Contains unit/integration tests verifying that `AgentSessionInfo` correctly serializes all summary fields (`current_activity`, `is_stalled`, `workflow_stage`, `turn_count`, `quota_percent`) and the `/api/agents` endpoint returns them properly.

---

## 3. Step-by-Step Implementation Guide

**Step 1: Build the Web Component (`agent-summary-overview.js` & `.css`)**
- Implement the `<agent-summary-overview>` element with a `sessions` property.
- For each session, render a card displaying: Title/Issue #, Status Badge (color-coded), `workflow_stage`, `current_activity`, `duration_seconds` (or started_at), and a progress bar for `quota_percent` & `turn_count` vs `max_turns`.
- Add visual indicators (e.g., pulsing dots) for `is_stalled` or active execution.
- Ensure clicking the card invokes `window.selectSession(session_id)` (or dispatches a custom event that `app.js` listens for).

**Step 2: Update `index.html`**
- Include the new CSS and JS files in the `<head>` and `<body>`.
- Insert a "View Dashboard" button (e.g., an icon next to the "Active Sessions" header in the sidebar).
- Insert `<agent-summary-overview id="global-dashboard" class="hidden"></agent-summary-overview>` inside the `#console-panel` section.

**Step 3: Wire Data in `app.js`**
- In `app.js`, add a function `showDashboardView()` that hides `#console-active` and `#console-empty`, clears `activeSessionId`, and unhides `#global-dashboard`.
- Attach a click listener to the new "View Dashboard" button to call `showDashboardView()`.
- Inside `handleWsMessage()` (on `init`, `session_created`, `session_updated`, `session_deleted`), after updating the `sessions` array, pass it to the dashboard: `const db = document.getElementById('global-dashboard'); if(db) db.sessions = sessions;`.
- Modify `selectSession()` to ensure `#global-dashboard` is hidden when an agent is selected.

**Step 4: Backend Contract Tests (`test_agent_summary.py`)**
- Create a test fixture to instantiate a mock `AgentSessionInfo` with various workflow stages, current activities, and stalled states.
- Test the `/api/agents` endpoint to confirm the JSON response includes all required keys for the dashboard to consume.

---

## 4. Verification & Testing Criteria

### A. Code & Test Execution
- **Run Unit Tests**: 
  - Execute `python -m pytest tests/test_agent_summary.py > test_summary.log 2>&1`
  - *Note*: Ensure the command log suppression rule is followed. Inspect the log using `Get-Content -Tail 40 test_summary.log` only if it fails, then delete the file.

### B. Visual & End-to-End Verification
1. **UI Layout**: Verify the "Dashboard Overview" button appears in the sidebar and clicking it displays the multi-agent grid.
2. **Real-time Sync**: Spawn a new simulated agent. Verify its card immediately appears on the dashboard without reloading the page.
3. **Data Accuracy**: Ensure the card displays the correct status, `workflow_stage`, current activity text, and turn/quota progress bars.
4. **Interactivity**: Click the agent's summary card and confirm the UI instantly switches to the detailed tab view for that specific agent.
