# 🤖 Agent Operational Guidelines: agent-manager

This repository is governed by the Antigravity Autonomous Agent Protocol. Any agent contributing to or developing within `agent-manager` MUST strictly adhere to these rules.

---

## 1. Mandatory Worktree Development (CRITICAL)
- **Zero Direct Edits in Main Checkout**: All feature development, bug fixes, refactoring, and updates to `agent-manager` MUST be executed inside an isolated git worktree located under `.worktrees/<branch-name>` (e.g., `.worktrees/feat-<feature-name>` or `.worktrees/issue-<number>`).
- **Worktree Setup Standard**:
  ```bash
  git worktree add -B "feat/<feature-name>" ".worktrees/feat-<feature-name>" origin/main
  ```
- **Isolated Testing**: Run and validate tests, lints, and syntax checks within the worktree.
- **Merge via PR / Clean Branch**: Commit changes on the feature branch, push, and create a Pull Request. Never modify the root `main` branch directly during feature work.

---

## 2. Command Log Suppression (User Global Rule)
- **Clean Execution Logs**: Never run verbose commands directly in the shell without redirection. Append `> <log_name>.log 2>&1` to keep task execution clean.
- **Inspect on Failure Only**: Read only the last 20-50 lines if exit code is non-zero. Clean up temporary logs immediately.

---

## 3. GitHub Project Board & Issue Rules
- **No Tag Modifications**: Never add, remove, or modify GitHub issue tags/labels (e.g. `agent:*`). All status transitions are managed purely via the GitHub Project Board columns.
- **Chat Stays Open Until 'Done'**: Agent sessions and chats must remain open in `IN_REVIEW` for continuous user feedback and testing until the card is explicitly moved to `✅ Done` on the Project Board.
- **Re-Queued Task Ingestion**: When an issue is moved back into `📋 Ready for Agent`, automatically inspect the issue for new user comments or requirement edits and feed them into the agent as continuation context.
