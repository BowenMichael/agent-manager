# Implementation Plan: Issue #58 (Per-Project Cron Dispatcher)

## 1. Architectural Overview
Currently, `ProjectBacklogDispatcher` halts backlog promotion globally if **any** active issue exists on **any** connected project board or if **any** local agent is running. This creates a bottleneck where multiple independent projects cannot progress concurrently.

To resolve this, the dispatch architecture will shift from a **global lock** to a **per-project lock**:
- **Data Grouping**: `fetch_board_items` will be refactored to group issues by their respective `project_id`.
- **Targeted Evaluation**: The dispatcher will iterate over each configured project. For each project, it will determine if it has active work (either marked as "In Progress"/"Ready" on the board OR currently being processed by a local agent).
- **Independent Promotion**: If a project is deemed idle, the dispatcher will promote one item from *that specific project's* backlog without affecting or being blocked by other projects.
- **Reporting**: The cron dispatch result structure will be updated to return a nested payload, reporting the status and actions taken per project.

## 2. Target Files & Modular Breakdown

All target files currently adhere to the strict under-250-line rule, and these modifications will keep them well within the threshold. No new monolithic files will be created.

### A. `agent_manager/cron/task_dispatcher.py`
- **Responsibility**: Fetching and parsing GitHub Project Board data.
- **Changes**: Refactor the item fetching logic to group parsed items by `project_id` rather than maintaining global active/backlog lists.

### B. `agent_manager/cron/scheduler.py`
- **Responsibility**: Orchestrating the dispatch loop and evaluating conditions.
- **Changes**: 
  - Remove the global early-exit triggered by local agents or active issues.
  - Correlate running local agents to specific projects by matching issue numbers and repository identifiers.
  - Implement a loop to evaluate and dispatch items for each project independently.
  - Update the `dispatch_history` result schema to support multi-project outcomes.

### C. `tests/test_dispatch_loop.py`
- **Responsibility**: Validating the cron loop logic.
- **Changes**: 
  - Update mocks to reflect the new return signature of the task dispatcher.
  - Add tests validating that a busy project does not block an idle project from receiving a backlog promotion.

## 3. Step-by-Step Implementation Guide

### Step 1: Refactor Board Item Fetching (`task_dispatcher.py`)
1. Modify `fetch_board_items` to return a dictionary mapping `project_id` to its state: `Dict[str, Dict[str, Any]]`.
2. The inner dictionary should contain:
   - `board_title`: The title of the board.
   - `active_items`: List of items with active statuses.
   - `backlog_items`: List of items with backlog statuses.
3. Ensure no global lists are used; append items only to their respective project's lists.

### Step 2: Refactor Dispatch Logic (`scheduler.py`)
1. In `ProjectBacklogDispatcher.check_and_dispatch`, fetch the grouped board data.
2. Collect all active local agent sessions. Instead of just saving session IDs, extract a set of composite identifiers (e.g., `(repo, str(issue_number))`) for all `RUNNING` or `INITIALIZING` agents.
3. Initialize a `results` dictionary to store outcomes per project.
4. Iterate over each `project_id` and its `data` in the fetched board data:
   - **Determine Activity**: 
     - Check if `len(data["active_items"]) > 0`.
     - Check if any item in `data["active_items"]` or `data["backlog_items"]` matches the composite keys of the running local agents.
   - **Handle Active Project**: If active, record `"status": "active_issue_present"` (or similar) in the `results` for this project and skip to the next.
   - **Handle Idle Project**: If idle and `len(data["backlog_items"]) > 0`, call `promote_backlog_issue` for the first backlog item. Record `"status": "dispatched"`.
   - **Handle Empty Backlog**: If idle and no backlog exists, record `"status": "backlog_empty"`.
5. Aggregate the project results into a top-level result (e.g., `{"status": "processed", "projects": results}`) and append to `self.dispatch_history`.

### Step 3: Update Unit Tests (`test_dispatch_loop.py`)
1. Update existing tests to mock `fetch_board_items` returning the new dictionary structure.
2. Update assertions to check the nested `projects` dictionary in the dispatch result.
3. **Add a new test**: Create a scenario with two projects (one active, one idle with a backlog). Verify that `promote_backlog_issue` is called *only* for the idle project and that the active project correctly skips.

## 4. Verification & Testing Criteria

### Expected Behavior
- The cron loop should evaluate each project board independently.
- If Project A has an agent running but Project B does not, Project B should still receive a promoted backlog issue.
- The `dispatch_history` array should clearly show actions taken per project in each run.

### Testing Protocol
Execute the following test command, strictly observing output suppression rules. Inspect the tail only if a failure occurs:

```powershell
# Run the dispatch loop test suite and redirect output
python -m unittest tests.test_dispatch_loop > test_dispatch.log 2>&1

# (Optional, only on failure) Inspect the last 40 lines:
# Get-Content -Tail 40 test_dispatch.log

# Cleanup logs
Remove-Item test_dispatch.log -ErrorAction SilentlyContinue
```

### Checklist
- [ ] `fetch_board_items` returns grouped data.
- [ ] `check_and_dispatch` processes projects individually.
- [ ] Local active agents are correctly matched to their respective projects.
- [ ] Unit tests pass and assert concurrent multi-project dispatch logic.
- [ ] Log outputs accurately reflect per-project activity.
