# Architecture & Implementation Plan: Issue #78 (Remove API Key Requirement)

## 1. Architectural Overview
The Antigravity application relies on the local CLI subscription (`~/.gemini/antigravity-cli/settings.json`) as its primary source of authentication for running agents. The Gemini API key is strictly an optional fallback for bypassing subscription quotas.

This fix focuses purely on the presentation and frontend behavior layers, as the core backend endpoints (`api/settings.py`) and agent dispatchers (`runners/spawner.py`) already support running without the API key and do not block execution. 

Key design decisions:
- **Presentation Layer Clean-up**: Remove the prominent HTML warning banner block from the main UI layout, eliminating the false signal that an API key is required.
- **Client Logic Decoupling**: Adjust `settings.js` so the absence of a Gemini API key simply reflects a "Not configured" state for the fallback, rather than triggering error UI visibility classes.
- **Copy Alignment**: Reword the Settings Modal label for the API Key input to explicitly denote it as an "Optional Fallback".

## 2. Target Files & Modular Breakdown
- `agent_manager/static/index.html` (UI templates)
- `agent_manager/static/modules/settings.js` (Client-side settings logic)

*Note: No modular decomposition/splitting is required for these changes as we are purely removing/updating existing logic within acceptable file length constraints.*

## 3. Step-by-Step Implementation Guide
**Step 1: HTML Layout Adjustment (`agent_manager/static/index.html`)**
- Search for the `<div class="api-key-banner hidden" id="api-key-banner">` (approx. line 95).
- Delete this entire HTML block (the wrapping div and its inner contents `⚠️ Gemini API Key Required...`).
- Locate the `<label>` for `input-gemini-key` in the Settings Modal (approx. line 792) currently reading `Google Gemini API Key (Bypasses Subscription Quota)`.
- Update the label text to: `Optional Fallback: Google Gemini API Key`.

**Step 2: Client Logic Adjustment (`agent_manager/static/modules/settings.js`)**
- Remove the initialization of the `apiKeyBanner` constant (approx. line 4): `const apiKeyBanner = document.getElementById('api-key-banner');`.
- Remove the conditional logic blocks responsible for toggling the `hidden` class on the banner:
  - `if (apiKeyBanner) apiKeyBanner.classList.add('hidden');`
  - `if (apiKeyBanner) apiKeyBanner.classList.remove('hidden');`
- Leave the `keyStatusDisplay` (green/amber) logic intact, as "Not configured" correctly represents the state of the fallback key without acting as a blocking error.

**Step 3: Verification Preparation**
- Do not make changes to `api/settings.py` or `runners/spawner.py`, but use them to test execution.

## 4. Verification & Testing Criteria
- **Visual Check (Banner)**: Start the server, clear `GEMINI_API_KEY` from configuration/`.env`, and load `http://localhost:8000/`. Confirm that no API key warning banner is displayed at the top of the dashboard.
- **Visual Check (Modal)**: Open the "Settings" modal. Confirm the API Key input label now reads "Optional Fallback: Google Gemini API Key".
- **Functional Backend Test**: Submit a new agent task (e.g., spawn an agent for a dummy issue) with no API Key provided. Ensure the backend returns a 200 OK and `agent_manager.runners.spawner` initializes the agent properly via the local subscription context.
- **Command Log Suppression**: When running tests or `npx` tools, redirect output (e.g., `npm run test > test_run.log 2>&1`) and inspect only the last 20 lines upon failure. Delete the logs when verified.
