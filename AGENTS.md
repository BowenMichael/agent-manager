# Autonomous Agent Guidelines & Budget Guardrails

This project follows the **Antigravity Autonomous Agent Protocol & Issue-Driven Development Lifecycle**. All AI agents operating in, or contributing to, `agent-manager` MUST strictly adhere to the following rules:

---

## 1. Mandatory Worktree Development & Task Lifecycle (CRITICAL)

### A. Git Worktree Isolation (Strictly Enforced)
To prevent interference with the developer's active editor, other agent sessions, or local uncommitted changes:
1. **Zero Direct Edits in Main Checkout**: All feature development, refactoring, and bug fixes MUST occur in an isolated Git worktree under `.worktrees/<branch-name>` (e.g. `.worktrees/feat-<feature-name>` or `.worktrees/issue-<number>`).
2. **Worktree Creation**:
   ```bash
   git worktree add -B "feat/<short-description>" ".worktrees/feat-<short-description>" origin/main
   ```
3. **Execution**:
   - All file edits, builds, tests, and commits must be scoped exclusively to the worktree directory.
4. **Completion & Cleanup**:
   - Push the branch from the worktree:
     ```bash
     git push origin feat/<short-description>
     ```
   - Open a Pull Request linking to the issue with visual proof, test logs, and acceptance criteria verification.
   - Clean up the worktree once the branch is merged/archived:
     ```bash
     git worktree remove .worktrees/feat-<short-description>
     ```

### B. Issue Takeover Notification
When picking up an issue from GitHub:
1. **Selection**: Look for issues with Project Board Status **`📋 Ready for Agent`**.
2. **Immediate Project Board Update**:
   - Move the card on the GitHub Project Board directly to **`⚡ In Progress`**.
   - **CRITICAL**: Do NOT add, remove, or modify GitHub issue labels/tags. Status transitions are managed purely via Project Board columns.
3. **Mandatory Issue Takeover Comment**:
   The agent **MUST immediately comment** on the GitHub issue to notify the team that development has commenced:
   ```markdown
   🤖 **Agent Takeover: Development Started**

   - **Worktree**: `.worktrees/issue-<number>`
   - **Branch**: `feat/issue-<number>-<short-description>`
   - **Planned Approach**:
     1. [Step 1: Implementation blueprint & file inspection]
     2. [Step 2: Core changes, unit tests, and validation]
     3. [Step 3: Verification, demo recording, and PR creation]
   - **Budget Guardrail**: Max 15 tool execution turns before pause & review.
   ```

### C. Issue & Project Board Synchronization (Anti-Duplication Protocol)
To ensure multiple agents or team members never duplicate work:
1. **Check Claim Status First**:
   - Before taking any action on an issue, verify it is strictly in `📋 Ready for Agent` state and has no active worktree in `.worktrees/`.
   - If an issue is already in `⚡ In Progress`, `🔍 In Review`, or has an active worktree, **DO NOT TOUCH IT**.
2. **Post Deliverables Directly to the GitHub Issue**:
   - **Never keep answers only in local IDE chat.**
   - All architecture specifications, deployment guides, research findings, and task completions must be posted as formal comments on the GitHub issue.
3. **Mark Acceptance Criteria Checkboxes**:
   - When criteria are satisfied, update the GitHub issue body via API to check off the boxes (`- [x]`).
4. **Move to Review**:
   - Once all criteria are met, move the card on the Project Board to **`🔍 In Review`**.

---

## 2. 🛑 Token & Complexity Budget Guardrail (Mandatory Pause)

To ensure tasks remain cost-effective and prevent run-away context/token consumption, the agent must enforce the following guardrail:

### Thresholds & Automated Circuit Breakers
- **Turn Limit (Enforced)**: If a single task reaches **15 tool execution turns** without completing the implementation, the runner halts execution automatically.
- **Duplicate Tool Call Circuit Breaker**: If the agent executes the exact same tool with identical arguments **3 consecutive times**, the runner terminates the process immediately to prevent infinite token spend.
- **Excessive File Reading Circuit Breaker**: If the agent performs **8 consecutive file view operations** without making any code edits or running tests, the runner pauses execution.
- **Token Budget**: If the session approaches the session token budget limit (default: 150,000 tokens).

### ⚡ Mandatory Tool Efficiency Directives (Anti-Loop Protocol)
To ensure context windows remain clean and prevent repetitive re-reading:
1. **Search Before Viewing**: Always use `grep_search` to pinpoint the exact function, class, or symbol location before calling `view_file`.
2. **Mandatory Line Range Slicing**: When calling `view_file`, ALWAYS specify `StartLine` and `EndLine` (maximum 100 lines per call). Never view entire files over 200 lines at once.
3. **Zero Redundant Re-Reading**: Never call `view_file` on the same file or lines you have already inspected within the active turn. Trust your context window.
4. **Action-Oriented Exploration**: Limit exploration to 3–4 targeted searches/reads before writing code or running tests.

### Mandatory Pause Protocol
When a threshold or circuit breaker is reached, execution is halted automatically:

1. **Post Insights Breakdown** (both as an Issue comment and in the dashboard stream):
   ```markdown
   ⚠️ **Task Paused: Token / Complexity Budget Threshold Reached**
   
   ### 📊 Task Insights
   - **Progress Completed**: [Summary of files edited and components built]
   - **Remaining Work**: [Exact items needed to reach acceptance criteria]
   - **Cost / Complexity Driver**: [Explain why token consumption or turn count is high]
   - **Proposed Next Action**: [Option A: Approve 15 more turns to finish; Option B: Narrow scope; Option C: Human intervention]
   ```
2. **Await User Approval**:
   - The agent MUST NOT take further code modification actions until the user explicitly responds with approval to proceed via the Agent Manager UI or GitHub comment.

---

## 3. Command Log Suppression (User Global Rule)
- **Suppress Verbose Output**: Never run build, test, typecheck, or lint commands directly in the shell without redirection if they produce verbose output. Instead, redirect their output to a temporary log file:
  ```powershell
  npm run test > test_run.log 2>&1
  npx tsc --noEmit > tsc_run.log 2>&1
  ```
- **Inspect on Failure Only**:
  - If the command succeeds (exit code `0`), do not output or read the log file.
  - If the command fails (exit code non-zero), view *only* the last 20 to 50 lines of the log file to diagnose the error:
    ```powershell
    Get-Content -Tail 40 test_run.log
    ```
- **Clean Up**: Delete temporary log files immediately once the check is complete:
  ```powershell
  Remove-Item test_run.log, tsc_run.log -ErrorAction SilentlyContinue
  ```

---

## 4. Chat Lifecycle & Re-Queued Task Ingestion
- **Chat Stays Open Until 'Done'**: Agent sessions and chats must remain open and interactive in `IN_REVIEW` for continuous user feedback, questions, and testing until the card is explicitly moved to `✅ Done` on the Project Board.
- **Re-Queued Task Ingestion**: When an issue is moved back into `📋 Ready for Agent`, the system automatically inspects the issue for new user comments or requirement edits and feeds them into the existing agent session as continuation context in its active worktree.
