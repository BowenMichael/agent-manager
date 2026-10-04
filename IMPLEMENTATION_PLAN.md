# Implementation Plan: Agent Tabs (GitHub Issue #1)

## 1. Architectural Overview
To provide dedicated tabbed navigation for Git and Issue context, we will expand the single Right Pane (`agent-overview-pane`) into a tabbed layout. The existing overview widgets will reside in the default tab. We will implement two new modular Web Components (`<git-tree-viewer>` and `<issue-viewer>`) injected into their respective tabs. To support these components, we will add two new backend API endpoints that fetch the necessary Git topology and GitHub Issue context based on the active `session_id`.

## 2. Target Files & Modular Breakdown
**Strict Anti-Monolith Directive**: No new file should exceed 250 lines. Decompose logic into dedicated components.

* **UI Structure & Routing**:
  * `agent_manager/static/index.html`: Update the `agent-overview-pane` to include tab headers and containers for the new components.
  * `agent_manager/static/app.js`: Add lightweight event listeners to handle tab switching (toggling `active`/`hidden` classes) and setting the `session-id` attribute on the web components.
  * `agent_manager/static/style.css`: Add styles for the tab headers.
* **New Web Components**:
  * `agent_manager/static/components/git-tree-viewer.js` / `.css`: Fetches and renders Git topology.
  * `agent_manager/static/components/issue-viewer.js` / `.css`: Fetches and renders the GitHub issue and conversation tree.
* **Backend APIs**:
  * `agent_manager/server.py`: Register two new GET endpoints: `/api/agents/{session_id}/git-tree` and `/api/agents/{session_id}/issue`.
  * `agent_manager/utils/git.py` (NEW): Helper to execute async Git commands in the agent's worktree.
  * `agent_manager/github.py`: Add `get_issue` and `get_issue_comments` functions to fetch data from the GitHub REST API.

## 3. Step-by-Step Implementation Guide

**Step 1: Backend Helpers (`github.py` & `utils/git.py`)**
- Create `agent_manager/utils/git.py` with an async function `get_git_tree(worktree_path: str)`. It should run `git log --graph --oneline --decorate --all -n 30` (or similar) via `asyncio.create_subprocess_exec` within the specified worktree path and return the raw stdout string.
- In `agent_manager/github.py`, add `get_issue(repo: str, issue_number: int)` and `get_issue_comments(repo, issue_number)` that use `httpx.AsyncClient` to hit the GitHub API (`/repos/{repo}/issues/{issue_number}` and its `/comments` endpoint). 

**Step 2: API Endpoints (`server.py`)**
- Implement `@app.get("/api/agents/{session_id}/git-tree")`. Retrieve the `AgentSessionInfo` from storage. If `worktree_path` exists, call `get_git_tree` and return it.
- Implement `@app.get("/api/agents/{session_id}/issue")`. Retrieve the session info. If `repo` and `issue_number` exist, fetch the issue details and comments via `github.py` and return them as a unified JSON payload.

**Step 3: Tabbed Layout (`index.html` & `app.js`)**
- In `index.html`, locate `div.agent-overview-pane`. Add a `.tabs-header` container with three buttons: "Overview" (default active), "Git Tree", and "Issue Context".
- Wrap the existing overview boxes in a `<div id="tab-overview" class="tab-content active">`.
- Add two new containers: `<div id="tab-git-tree" class="tab-content hidden"><git-tree-viewer></git-tree-viewer></div>` and `<div id="tab-issue" class="tab-content hidden"><issue-viewer></issue-viewer></div>`.
- In `app.js`, implement a function to handle tab clicks, toggling visibility. When a session is selected, ensure the active `session_id` is passed as an attribute to the `<git-tree-viewer>` and `<issue-viewer>` custom elements.

**Step 4: Web Components (`static/components/`)**
- **Git Tree Viewer**: Create a custom element that listens for `session-id` attribute changes. When updated, fetch `/api/agents/{session_id}/git-tree` and render the output in a monospaced `<pre>` block or stylized tree UI.
- **Issue Viewer**: Create a custom element that fetches `/api/agents/{session_id}/issue`. Render the issue title, body, and comments. Leverage the existing `marked.js` and `purify.js` (loaded in `index.html`) to render the Markdown content safely.

## 5. Verification & Testing Criteria
- **Validation Execution**:
  - Run the server `python main.py` or `uvicorn agent_manager.server:app` (or backend equivalents).
  - Open the UI and select an active agent session that has an associated issue number and worktree.
  - Verify tab switching works seamlessly without disrupting the live terminal stream on the left pane.
  - Verify the Git Tree tab displays accurate topology reflecting the worktree branch relative to main.
  - Verify the Issue Context tab renders GitHub Markdown correctly, displaying both the main issue body and subsequent conversation.
- **Log Suppression Rule**: If running backend tests, ensure outputs are redirected (`pytest > test_pytest.log 2>&1`) and clean up the log on success.
- **Visual Proof**: Capture screenshots demonstrating both the Git Tree and Issue tabs rendering actual data, and link them in the final GitHub issue comment.
