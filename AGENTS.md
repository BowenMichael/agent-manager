# Autonomous Agent Guidelines & Budget Guardrails

This project follows an **Autonomous, Issue-Driven Development Lifecycle**. All AI agents operating in this repository must strictly adhere to the following rules:

---

## 1. Autonomous Task Lifecycle & Worktree Isolation

### A. Issue Takeover Notification
When picking up an issue from GitHub:
1. **Selection**: Look for issues labeled `agent:ready`.
2. **State Transition**:
   - Remove label `agent:ready`.
   - Add label `agent:in-progress`.
3. **Mandatory Issue Takeover Comment**:
   The agent **MUST immediately comment** on the GitHub issue to notify the team that work has begun:
   ```markdown
   🤖 **Agent Takeover: Development Started**

   - **Worktree**: `.worktrees/issue-<number>`
   - **Branch**: `feat/issue-<number>-<short-description>`
   - **Planned Approach**:
     1. [Step 1: Implementation blueprint]
     2. [Step 2: Core changes & testing]
     3. [Step 3: Verification & demo recording]
   - **Budget Guardrail**: Max 15 tool execution turns before pause & approval.
   ```

### B. Git Worktree Isolation (Strictly Required)
To prevent interference with the developer's active editor, other agent sessions, or local uncommitted changes:
1. **Never work in the root directory**: All feature development must occur in an isolated Git worktree.
2. **Worktree Creation**:
   ```bash
   git worktree add -b feat/issue-<number>-<short-description> .worktrees/issue-<number> master
   ```
3. **Execution**:
   - All file edits, builds, tests, and commits must be scoped to `.worktrees/issue-<number>`.
4. **Completion & Cleanup**:
   - Push the branch from the worktree:
     ```bash
     git push origin feat/issue-<number>-<short-description>
     ```
   - Open the Pull Request linking to the issue with demo video and screenshots.
   - Clean up the worktree once the branch is pushed:
     ```bash
     git worktree remove .worktrees/issue-<number>
     ```
   - Tag the issue with `agent:review`.

### C. Issue & Project Board Synchronization (Anti-Duplication Protocol)
To ensure multiple agents or team members never duplicate work:
1. **Check Claim Status First**:
   - Before taking any action on an issue, verify it is strictly in `agent:ready` state and has no active worktree in `.worktrees/`.
   - If an issue is already labeled `agent:in-progress`, `agent:needs-approval`, or has an active worktree, **DO NOT TOUCH IT**.
2. **Immediate Project Board Update**:
   - Move the card on the GitHub Project Board to **`⚡ In Progress`** upon takeover.
3. **Always Post Deliverables Directly to the GitHub Issue**:
   - **Never keep answers only in local IDE chat.**
   - All architecture specifications, deployment guides, research findings, and task completions must be posted as formal comments on the GitHub issue.
4. **Mark Acceptance Criteria Checkboxes**:
   - When criteria are satisfied, the agent MUST update the GitHub issue body via API to check off the boxes (`- [x]`).
5. **Move to Review**:
   - Once all criteria are met, update the issue labels to `agent:review` and move the card on the Project Board to **`🔍 In Review`**.

---

## 2. 🛑 Token & Complexity Budget Guardrail (Mandatory Pause)

To ensure tasks remain cost-effective and prevent run-away context/token consumption, the agent must enforce the following guardrail:

### Thresholds
- **Turn Limit**: If a single task reaches **15 tool execution turns** without completing the implementation.
- **Context / Token Growth**: If the conversation encounters repetitive failure loops, unexpected circular dependencies, or major unplanned refactoring.

### Mandatory Pause Protocol
When a threshold is reached, the agent **MUST IMMEDIATELY PAUSE** execution on the issue and execute the following:

1. **Tag the Issue**:
   - Remove `agent:in-progress`.
   - Add `agent:needs-approval`.
2. **Post Insights Breakdown** (both as an Issue comment and to the user):
   ```markdown
   ⚠️ **Task Paused: Token / Complexity Budget Threshold Reached**
   
   ### 📊 Task Insights
   - **Progress Completed**: [Summary of files edited and components built]
   - **Remaining Work**: [Exact items needed to reach acceptance criteria]
   - **Cost / Complexity Driver**: [Explain why token consumption is high]
   - **Proposed Next Action**: [Option A: Approve 10 more turns to finish; Option B: Narrow scope; Option C: Human intervention]
   ```
3. **Await User Approval**:
   - The agent MUST NOT take further code modification actions until the user explicitly responds with approval to proceed.
