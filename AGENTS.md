# 🤖 Agent Operational Guidelines: agent-manager

This repository is governed by the Antigravity Autonomous Agent Protocol. Any agent contributing to or running within `agent-manager` MUST strictly adhere to these rules.

---

## 1. Core Principles
- **No Work in Main/Master**: Always execute development tasks inside an isolated worktree under `.worktrees/issue-<number>`.
- **Command Log Suppression**: Always redirect verbose command outputs (tests, linters, builds) to temporary `.log` files. Read only on failure, and clean up afterwards.
- **Budget Guardrails**: Do not exceed 15 tool turns without posting a progress insight and awaiting approval if an issue is blocked.

---

## 2. Agent Manager Specific Rules
- **Non-blocking Dispatch**: The webhook receiver must immediately acknowledge webhooks with HTTP 200/201 and offload agent execution to background asyncio tasks.
- **Graceful Context Queuing**: Never interrupt ongoing tool executions abruptly when injecting context; append to the session queue so the agent ingests the context on its next conversational step.
- **Safe Worktree Cleanup**: Upon completion of an issue, verify that the PR has been opened and changes committed before pruning worktrees.
