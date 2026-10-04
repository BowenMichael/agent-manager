# Architecture Plan: GitHub Issue #30 — Target Repos Based on Issue

## 1. Architectural Overview
The current system hardcodes local paths and fallback default repositories (e.g., `BowenMichael/f1-frontend` and `WORKSPACE_BASE / "F1 Front End"`) when setting up worktrees and responding to webhook events. 

To enable dynamic repository identification and workspace resolution:
1. **Dynamic Workspace Resolution**: Extract directory scanning logic from both `runner.py` and `worker.py` into a new modular utility file. This utility will take a GitHub repository full name (e.g., `BowenMichael/agent-manager`) and search `WORKSPACE_BASE` up to a limited depth for a matching local repository checkout. It will validate the match by checking for a `.git` folder and ideally inspecting `.git/config` for the matching remote URL.
2. **Payload Parsing Enhancements**: Update `agent_manager/webhooks.py` to ensure all relevant events (`issues`, `issue_comment`, `projects_v2_item`) dynamically extract and pass the repository full name (e.g., `payload.repository.full_name`) to the `SpawnRequest`.
3. **Decoupled Execution**: By consolidating the resolution logic in `agent_manager/utils/workspace.py`, both the server (`runner.py`) and the CLI worker process (`worker.py`) remain consistent, avoiding hardcoded monoliths, and maintaining strict line limits per the anti-monolith rule.

## 2. Target Files & Modular Breakdown
- **Create: `agent_manager/utils/workspace.py` (New File)**
  - Dedicated file for file system path resolution.
  - Expected size: ~50 lines.
  - Single Responsibility: Locate and return the `Path` of a local git repository given a `repo_full_name` string.
- **Modify: `agent_manager/runner.py` (Existing, >1500 lines)**
  - Update `_setup_worktree` method. Remove the hardcoded `candidate_dirs` list and use the new helper function.
- **Modify: `agent_manager/worker.py` (Existing, 100 lines)**
  - Update Phase 1 workspace validation. Remove the duplicated `candidate_dirs` array and invoke the new utility.
- **Modify: `agent_manager/webhooks.py` (Existing, ~250 lines)**
  - Update `process_github_event` specifically around the `projects_v2_item` branch (and review others) to dynamically extract the target repo instead of strictly using `DEFAULT_REPO`.
- **Create: `tests/test_workspace.py` (New File)**
  - Unit tests to validate the `find_local_workspace` logic, using mocks for filesystem traversal.

## 3. Step-by-Step Implementation Guide

### Step 1: Implement the Workspace Resolver Module
1. Create `agent_manager/utils/workspace.py`.
2. Import necessary modules (`os`, `configparser`, `pathlib.Path`, `agent_manager.config.WORKSPACE_BASE`).
3. Define `find_local_workspace(repo_full_name: str) -> Optional[Path]`:
   - Return early if `repo_full_name` is empty.
   - Extract the `repo_name` (the part after the slash).
   - Use `os.walk` starting at `WORKSPACE_BASE` (and explicitly limiting depth to 2 or 3 to avoid performance degradation).
   - Skip known large/non-source directories like `node_modules`, `venv`, `.git`.
   - Identify candidate directories matching the `repo_name`.
   - Confirm it is a git repository (has a `.git` folder).
   - (Optional but recommended) Validate the repository by checking if `.git/config` contains the `repo_full_name` in its remote origin URL.
   - Return the validated `Path` or `None`.

### Step 2: Refactor Agent Runner
1. In `agent_manager/runner.py`, import `find_local_workspace`.
2. Locate `_setup_worktree(self, repo: str, issue_number: int)`.
3. Strip out the `candidate_dirs` array containing hardcoded paths like `"F1 Front End"`.
4. Call `repo_dir = find_local_workspace(repo)`.
5. Proceed with worktree setup using this resolved `repo_dir`.

### Step 3: Refactor Terminal Worker
1. In `agent_manager/worker.py`, import `find_local_workspace`.
2. Locate the "Phase 1: Validating isolated git worktree..." block.
3. Remove the duplicated `candidate_dirs` list.
4. Replace it with a call to `repo_dir = find_local_workspace(args.repo)`.

### Step 4: Enhance Webhooks for Dynamic Repo Targeting
1. In `agent_manager/webhooks.py`, inspect `process_github_event`.
2. Ensure `repo = payload.get("repository", {}).get("full_name", DEFAULT_REPO)` is consistently used.
3. For the `projects_v2_item` event handler, if the payload contains `repository` data, extract it. If it doesn't, ensure `DEFAULT_REPO` is used gracefully, but prioritize the dynamic repository name whenever the payload allows.
4. Ensure `SpawnRequest` receives this dynamic `repo` rather than a hardcoded default.

## 4. Verification & Testing Criteria

### Testing Procedure
1. **Unit Tests**: Implement `tests/test_workspace.py` mocking `os.walk` and `.git/config` content to verify correct path resolution for both fast paths and deep searches.
2. **Execution**: Run the unit test using log suppression:
   ```powershell
   pytest tests/test_workspace.py > pytest_run.log 2>&1
   ```
3. **Failure Inspection**: If the command fails, view only the last 40 lines:
   ```powershell
   Get-Content -Tail 40 pytest_run.log
   ```
4. **Cleanup**: Remove temporary logs:
   ```powershell
   Remove-Item pytest_run.log -ErrorAction SilentlyContinue
   ```

### Acceptance Criteria Checklist
- [ ] No monolithic file created (All new files are under 250 lines).
- [ ] Path resolution logic is unified in `agent_manager/utils/workspace.py`.
- [ ] Hardcoded directory fallbacks are removed from `runner.py` and `worker.py`.
- [ ] Incoming webhooks seamlessly use the repository full name to build correct worktrees without assuming the fallback repository.
- [ ] Test cases pass correctly validating that dynamic repository names map to correct local folder paths.
