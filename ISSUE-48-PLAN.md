# Architectural Implementation Plan: Autonomous Dispatch Loop (Issue #48)

## 1. Architectural Overview

### **Objective**
Implement a self-sustaining autonomous dispatch loop. When an agent finishes its work (either successfully completing, failing, or pausing for review), the system should verify if all agents are idle. If the system is completely idle (zero active agents and zero active tasks on the project board), it automatically pulls the highest-priority issue from the backlog, marks it as `Ready for Agent`, and triggers the workflow.

### **Conceptual Approach & Component Interactions**
1. **Idle State Verification:** The system must strictly enforce that an auto-dispatch only occurs when the entire engine is idle. We will augment the existing `ProjectBacklogDispatcher` to first check the `AgentRunnerManager` for any sessions in `RUNNING` or `INITIALIZING` states. 
2. **Lifecycle Hooks (Event-Driven Triggers):** Instead of relying purely on a cron interval, we will embed background hooks into the agent's termination lifecycle (`stop_agent`, `complete_agent`, `archive_agent`, and `handle_post_process`). 
3. **Debounced Execution:** The trigger hook will include a short delay (e.g., 5 seconds) to allow the GitHub APIs, Git worktree teardowns, and status updates to propagate before executing the dispatch check.
4. **Self-Update Preservation:** The existing `check_and_update_agent_manager()` logic will remain intact as the first step of the dispatch loop, ensuring the system always updates to the latest main branch version when idle.

### **Key Design Decisions**
- **Decoupled Trigger Service:** To adhere to the strict anti-monolith rule and avoid adding complexity/circular imports to `lifecycle.py`, the trigger logic will be abstracted into a new dedicated service file (`dispatch_trigger.py`).
- **Inline Dependency Resolution:** The `ProjectBacklogDispatcher` will resolve `AgentRunnerManager` inline to prevent cyclic imports between the cron scheduler and the runner core.

---

## 2. Target Files & Modular Breakdown

| File Path | Action | Description |
|-----------|--------|-------------|
| `agent_manager/services/dispatch_trigger.py` | **Create** | **(New)** A lightweight, single-responsibility service that exposes `fire_dispatch_hook()`. It abstracts `asyncio.create_task` and the delay logic away from the runners. |
| `agent_manager/cron/scheduler.py` | **Modify** | Add an async `trigger_dispatch_now(delay_seconds)` method to `ProjectBacklogDispatcher`. Enhance `check_and_dispatch()` to validate `active_agents == 0` via `AgentRunnerManager`. |
| `agent_manager/runners/lifecycle.py` | **Modify** | Wire `fire_dispatch_hook()` into `stop_agent`, `complete_agent`, and `archive_agent`. |
| `agent_manager/runners/post_turn.py` | **Modify** | Wire `fire_dispatch_hook()` into `handle_post_process` when transitioning to `IN_REVIEW` or `FAILED`. |
| `tests/test_dispatch_loop.py` | **Create** | **(New)** Unit tests verifying the zero-active-agent verification and the debounce trigger. |

*Note: All files must remain under the 250 LOC limit constraint.*

---

## 3. Step-by-Step Implementation Guide

### **Step 1: Implement Local Idle Verification (`scheduler.py`)**
1. In `ProjectBacklogDispatcher.check_and_dispatch()`, insert a check at the very beginning (before fetching board items or running updates).
2. Use an inline import for `AgentRunnerManager` to get the singleton instance.
3. Calculate the number of active agents (sessions where `status` is `AgentStatus.RUNNING` or `AgentStatus.INITIALIZING`).
4. If the active agent count `> 0`, log a clear message (e.g., `"[Cron Dispatcher] Local agents are currently active. Skipping auto-dispatch."`) and return an early payload `{ "status": "agents_running" }`.
5. Add `trigger_dispatch_now(self, delay_seconds: int = 5)` that sleeps for `delay_seconds`, then `await self.check_and_dispatch()`.

### **Step 2: Create the Decoupled Trigger Service (`dispatch_trigger.py`)**
1. Create `agent_manager/services/dispatch_trigger.py`.
2. Define a function `fire_dispatch_hook(delay_seconds: int = 5)` that instantiates `ProjectBacklogDispatcher` and spawns an `asyncio.create_task` invoking `trigger_dispatch_now()`.
3. Catch and log any broad exceptions within the task to prevent background task panics.

### **Step 3: Wire the Lifecycle Hooks (`lifecycle.py` & `post_turn.py`)**
1. Import `fire_dispatch_hook` into `agent_manager/runners/lifecycle.py` and `agent_manager/runners/post_turn.py`.
2. **In `lifecycle.py`**: Call `fire_dispatch_hook()` at the very end of `stop_agent`, `complete_agent`, and `archive_agent` (after all state changes have been saved and broadcasted).
3. **In `post_turn.py`**: Call `fire_dispatch_hook()` inside `handle_post_process` if the session transitions to `IN_REVIEW` or `FAILED`.

### **Step 4: Edge Case Handling**
- Ensure that multiple rapid completions do not queue up redundant dispatches. The existing `fetch_board_items` validation inherently protects against this by skipping if an issue is already marked `Ready for Agent` or `In Progress`.

---

## 4. Verification & Testing Criteria

### **Expected Behavior**
1. When a running agent completes its turn and transitions to `IN_REVIEW`, the logs should indicate the dispatch hook fired.
2. 5 seconds later, the dispatcher checks `active_agents == 0`.
3. It polls the GitHub project board. If no issues are `In Progress` or `Ready for Agent`, it pulls the topmost `Backlog` issue, transitions it to `Ready for Agent`, and logs success.

### **Verification Checklist**
- [ ] `check_and_dispatch()` correctly calculates `active_agents == 0` and bails out if agents are running.
- [ ] `fire_dispatch_hook()` operates asynchronously without blocking agent shutdown.
- [ ] Log suppression rules are strictly followed when testing.

### **Test Commands (Command Log Suppression Applied)**
To manually verify without bloating the terminal output, the implementation model should execute the following when writing tests:
```powershell
# Run the dispatch unit tests and suppress output
pytest tests/test_dispatch_loop.py > test_run.log 2>&1

# Inspect on failure (only if exit code is non-zero)
if ($LASTEXITCODE -ne 0) { Get-Content -Tail 40 test_run.log }

# Cleanup
Remove-Item test_run.log -ErrorAction SilentlyContinue
```
