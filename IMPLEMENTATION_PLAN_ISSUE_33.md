# Implementation Plan: GitHub Issue #33 (Agent GitHub Deep Links)

## 1. Architectural Overview

**Objective**: Enable users to navigate directly from the Agent Manager UI to external GitHub entities by adding direct, actionable links to the tracked GitHub Issue and the corresponding Pull Request (if one exists).

**Approach**:
1. **Backend Payload Expansion**: We will extend the core backend state model (`AgentSessionInfo` in `models.py`) to expose `pr_url` and `pr_number` optionally alongside the existing `issue_number`. This guarantees the UI has all data needed to construct valid GitHub URLs.
2. **Global Summary Dashboard Upgrade**: We will modify the `<agent-summary-overview>` Web Component (`agent-summary-overview.js`) to render the issue number as a clickable hyperlink pointing to GitHub (`https://github.com/{owner}/{repo}/issues/{issue_number}`). If a PR exists for the session, a dynamic PR badge linking directly to the PR will be appended.
3. **Active Session Header Upgrade**: We will update the active session view header (in `index.html` and `app.js`) to include anchor tags within the session sub-meta row. These tags will dynamically display Issue and PR links when the payload contains the relevant data, and remain gracefully hidden when absent.
4. **Data Contract Testing**: We will update or add a backend unit test to explicitly verify that the extended session attributes (`issue_number`, `pr_url`, `pr_number`) successfully serialize through the FastAPI JSON endpoint to the frontend.

---

## 2. Target Files & Modular Breakdown

*Strict Anti-Monolith Rule: All files remain under 250 lines and logic must be modular.*

**Backend Domain Model & Tests**:
- **MODIFY**: `agent_manager/models.py`
  - Enhance `AgentSessionInfo` to include `pr_url: Optional[str] = None` and `pr_number: Optional[int] = None`.
- **MODIFY**: `tests/test_agent_summary.py` (or `test_manager.py`)
  - Add assertions verifying that the new PR attributes properly serialize in the `/api/agents` payload.

**Frontend UI Components**:
- **MODIFY**: `agent_manager/static/index.html`
  - In the `<div class="session-submeta">` section of the active agent header (around line 185), insert placeholder `<a href="..." id="current-issue-link" target="_blank" class="submeta-item hidden">` elements and `span` dividers for the Issue and PR links.
- **MODIFY**: `agent_manager/static/app.js`
  - In the session DOM update function (around line 557 where `currentRepo.textContent = session.repo` is set), locate the new link elements by ID.
  - Hydrate them with `href` values derived from `session.issue_number` and `session.pr_url` respectively. Remove their `hidden` CSS class if the data is present, otherwise apply the `hidden` class.
- **MODIFY**: `agent_manager/static/components/agent-summary-overview.js`
  - Inside `renderCard(s)`, update the `<div class="summary-card-id">` generation logic.
  - Transform the issue number string into an `<a>` tag pointing to `https://github.com/${s.repo}/issues/${s.issue_number}`.
  - Append an optional PR link anchor tag if `s.pr_url` exists.
  - Ensure links include `target="_blank"` and `onclick="event.stopPropagation()"` to prevent triggering the card's parent click listener.

---

## 3. Step-by-Step Implementation Guide

**Step 1: Backend Model Extension (`models.py`)**
- Add `pr_url: Optional[str] = None` and `pr_number: Optional[int] = None` to the `AgentSessionInfo` Pydantic model. 

**Step 2: Update Active Session Header UI (`index.html`)**
- Open `index.html` and locate the `session-submeta` container (around line 185).
- Insert hidden hyperlink nodes (and separator dots) for the GitHub Issue and PR:
  ```html
  <a href="#" target="_blank" class="submeta-item hidden" id="current-issue-link" style="color: var(--accent-cyan); text-decoration: none;">Issue</a>
  <span class="submeta-divider hidden" id="current-issue-divider">•</span>
  <a href="#" target="_blank" class="submeta-item hidden" id="current-pr-link" style="color: var(--accent-cyan); text-decoration: none;">PR ↗</a>
  <span class="submeta-divider hidden" id="current-pr-divider">•</span>
  ```

**Step 3: Wire Logic in UI Controller (`app.js`)**
- Locate the UI update logic for the active session (around line 557).
- If `session.issue_number` is present, construct the GitHub URL (`https://github.com/${session.repo}/issues/${session.issue_number}`), assign it to `current-issue-link`, set the text (e.g., `Issue #${session.issue_number} ↗`), and unhide the link/divider.
- Do the same for `current-pr-link` utilizing `session.pr_url` and `session.pr_number`. Hide elements if data is absent.

**Step 4: Enhance the Dashboard Web Component (`agent-summary-overview.js`)**
- Modify `renderCard(session)` to build actionable links instead of static text in the `summary-card-id` class element.
- The link must use `target="_blank"` and block event propagation so that clicking the link doesn't unintentionally navigate the main interface.

**Step 5: Backend Contract Tests (`tests/...`)**
- Initialize a mock `AgentSessionInfo` in the test suite populated with `issue_number`, `pr_url`, and `pr_number`.
- Test the `/api/agents` endpoint payload to ensure the properties serialize down to the frontend properly.

---

## 4. Verification & Testing Criteria

### A. Code & Test Execution
- **Run Unit Tests**: 
  - Execute `pytest tests/test_agent_summary.py > pytest_summary.log 2>&1`
  - *Note*: Ensure the command log suppression rule is followed. Inspect the log using `Get-Content -Tail 40 pytest_summary.log` only if it fails, then delete the file.

### B. Visual & End-to-End Verification
1. **Dashboard Overview Verification**: Start the server and create a simulated agent session with an issue number and a mock PR URL. Open the Dashboard Overview. Verify the issue number is a clickable blue link pointing to the correct repository and that a PR badge is clearly visible. Clicking either should open a new tab.
2. **Active Session Verification**: Navigate to the agent's detailed view. Look at the sub-meta bar below the header. The Issue link and PR link should be cleanly inserted between the existing repository and branch items.
3. **Absence Handling**: Start another agent session *without* an issue number or PR link. Verify that neither the dashboard card nor the active session view show broken link icons or "undefined" text. The items should be fully hidden or cleanly omit the PR badge.
