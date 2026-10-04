# Implementation Plan: Agent Comment Labeling (GitHub Issue #7)

## 1. Architectural Overview
To satisfy the requirement of clearly distinguishing automated agent comments from human developer comments, we will introduce a central comment formatting module (`agent_manager/formatters/comments.py`). This module will act as the single source of truth for constructing unified comment headers (e.g., `🤖 **Agent Update**`) and metadata footers (containing session ID and worktree context). 

We will refactor `agent_manager/runner.py` to route all its system-generated posts (circuit breaker halts, turn limits, and completion reports) through this new formatter. To handle initial takeover comments without relying on unpredictable agent MCP tool invocations, we will inject explicit formatting instructions into the prompt constructed in `agent_manager/poller.py` and `agent_manager/webhooks.py`, mandating the agent to append the exact footer when posting via MCP. Furthermore, we will update the developer guidelines in `AGENTS.md`. Finally, the webhook filter (`agent_manager/webhooks.py`) will be updated to use a shared `is_agent_comment` utility from the new formatter to reliably identify and drop agent-authored events, preventing feedback loops.

## 2. Target Files & Modular Breakdown
**Strict Anti-Monolith Directive**: No new file should exceed 250 lines. Decompose logic into dedicated components.

* **Formatters Module (New)**:
  * `agent_manager/formatters/comments.py`: Contains `format_agent_comment` to inject headers/footers and `is_agent_comment` to validate them.
* **Runner Module**:
  * `agent_manager/runner.py`: Update automated GitHub comments to use the new formatter.
* **Poller & Webhooks (Prompt Injection)**:
  * `agent_manager/poller.py`: Inject the required footer string into the initial user prompt so that any manual agent comments conform to the standard.
  * `agent_manager/webhooks.py`: Inject the required footer string for issue_comment trigger prompts, and update the self-comment filter condition.
* **Documentation**:
  * `AGENTS.md`: Update Section 1.B to reflect the new standardized takeover format.
* **Tests (New)**:
  * `tests/test_comment_formatters.py`: Unit tests for the new formatting logic.

## 3. Step-by-Step Implementation Guide

**Step 1: Create the Formatter Module**
- Create `agent_manager/formatters/comments.py`.
- Define `format_agent_comment(status: str, title: str, body: str, session_id: str, worktree_path: str = None) -> str`.
  - It should prepend a header: `🤖 **Agent {status}**: {title}`.
  - It should append a footer: `\n\n---\n*Posted automatically by Agent Manager | Session: {session_id} | Worktree: {worktree_path}*`.
- Define `is_agent_comment(body: str) -> bool` that returns `True` if the body contains the signature (e.g. checks for the footer text `*Posted automatically by Agent Manager` or standard headers `🤖 **Agent`).

**Step 2: Update Runner System Posts**
- In `agent_manager/runner.py`, import `format_agent_comment`.
- Locate the circuit breaker pause block (~line 1167), the turn budget limit block (~line 1247), and the agent completion update block (~line 1320).
- Replace the inline manual string formatting with `format_agent_comment`, passing the appropriate `status` (e.g., `"Paused"`, `"Update"`), `title`, `body`, `session_id`, and `worktree_path`.

**Step 3: Enforce Footer for Agent-Initiated Posts**
- In `agent_manager/poller.py` (around line ~400), modify the `prompt` string to explicitly instruct the agent: 
  `"When posting comments to the issue using MCP (like the Takeover comment), you MUST append this exact footer: \n---\n*Posted automatically by Agent Manager*"`
- Make an equivalent update in `agent_manager/webhooks.py` where context prompts are generated for new issue comments.
- Update `AGENTS.md` section 1.B (Mandatory Issue Takeover Comment) to show the new standardized footer.

**Step 4: Align Webhook Filter**
- In `agent_manager/webhooks.py` (~line 109), import `is_agent_comment`.
- Replace the hardcoded `if body.startswith("🤖 **Agent")...` with `if is_agent_comment(body): return {"status": "ignored", "reason": "agent_self_comment"}`.

**Step 5: Write Unit Tests**
- Create `tests/test_comment_formatters.py` and write test cases validating both the formatting and detection logic of the new module. 

## 4. Verification & Testing Criteria
- **Formatting Validation**: `pytest tests/test_comment_formatters.py > test_run.log 2>&1` -> Verify exit code 0.
- **Webhook Filter Regression**: If any existing webhook tests exist, run them to ensure agent-authored payloads return `{"status": "ignored"}`.
- **Command Log Suppression**: Inspect `test_run.log` only on failure using `Get-Content -Tail 40`. Delete logs upon success.
- **Visual Verification**: Run the application locally, trigger an agent via a project board move, and observe the initial Takeover comment and a subsequent Pause or Completion comment on a test issue to verify the footer renders properly.
