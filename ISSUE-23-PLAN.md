# Implementation Plan for Issue #23: Interactive Context Injection & Control Actions

## 1. Architecture Overview
The goal of this issue is to enhance the existing frontend with rich, interactive control over the agent session. This brings real-time interactive context injection (allowing the user to send messages to the agent) and granular lifecycle controls (Stop, Resume, Restart, Force Complete). The architecture must remain modular and clean.

Key functional pieces:
- **Interactive Context Injection**: A new bottom chat input component (`ContextInputBar.tsx`) that triggers `POST /api/agents/{id}/context` and optimistically injects a temporary "user bubble" in the transcript stream.
- **Enhanced Action Controls**: Updating `AgentControls.tsx` to include `Resume` and ensuring all destructive or important actions (Stop, Restart, Force Complete) pass through a confirmation modal hook or component before hitting the backend.
- **Model/Effort Selector**: A new modal (`ModelSelectorModal.tsx`) providing an interface to adjust thinking parameters (Model & Effort) for subsequent prompt turns.
- **Toast Notifications**: Integrating a toast notification system (`react-toastify` or a custom context) for success/failure feedback on agent control actions, replacing standard `alert()` calls.

## 2. Target Files

New Files (All under 250 lines):
- `frontend/src/components/control/ContextInputBar.tsx`: The bottom chat bar for context injection.
- `frontend/src/components/control/ModelSelectorModal.tsx`: Modal for selecting the model and effort level.
- `frontend/src/components/common/ConfirmationModal.tsx`: Reusable confirmation modal.
- `frontend/src/components/common/ToastNotifications.tsx`: Shared notification components (if using custom toasts) or configuration for a library.

Modified Files:
- `frontend/src/components/control/AgentControls.tsx`: Add "Resume" action, replace `alert` with toast, wire up `ConfirmationModal`.
- `frontend/src/services/apiClient.ts`: Add endpoint mappings for `/api/agents/{id}/context` and update any missing lifecycle endpoints.
- `frontend/src/components/stream/TranscriptStream.tsx` (or similar file): Add optimistic UI capabilities.
- `frontend/package.json`: Add toast notification library (e.g., `react-hot-toast` or `react-toastify`) if not existing.
- `CHANGELOG.md`: Update for release tracking.

## 3. Step-by-Step Implementation Guide

**Step 1: Scaffolding and Dependencies**
- Evaluate the existing project for a toast/notification system. If missing, install a lightweight library like `react-hot-toast`.
- Create the reusable `ConfirmationModal.tsx` utilizing existing UI patterns.

**Step 2: Interactive Context Injection**
- Implement `ContextInputBar.tsx`.
- Update `apiClient.ts` to include `injectAgentContext(sessionId, content)`.
- Update the session view (e.g. `AgentDetail.tsx` or similar) to render `ContextInputBar` at the bottom of the screen.
- Implement optimistic UI updates in the transcript view when sending context.

**Step 3: Action Controls with Confirmations & Toasts**
- Refactor `AgentControls.tsx` to remove `window.alert()` calls and replace them with toast notifications.
- Wrap `handleStop`, `handleRestart`, and `handleComplete` in a confirmation prompt utilizing `ConfirmationModal`.
- Add `handleResume` logic mapped to the resume API endpoint.

**Step 4: Model & Effort Level Selector Modal**
- Build `ModelSelectorModal.tsx`.
- Update the UI to include a "Settings" or "Model" button launching this modal.
- Map the save action to update the agent's parameters via an API call (e.g. `PATCH /api/agents/{id}`).

**Step 5: CHANGELOG Updates**
- Update the repository `CHANGELOG.md` under `[Unreleased]` with a summary of these new controls.

## 4. Verification & Testing Criteria
- **Context Injection**: Verify text submitted in the input bar appears instantly in the transcript (optimistic UI) and persists after page refresh.
- **Confirmation Modals**: Verify Stop, Restart, and Force Complete require a two-step confirmation process.
- **Model Selector**: Verify changing the model triggers an API call and correctly reflects in the UI.
- **Toast Feedback**: Verify that successful actions trigger green success toasts, and network/backend errors trigger red error toasts.
- **Anti-Monolith Check**: Ensure no file exceeds the 250-line limit.

## 5. Updating CHANGELOG.md under [Unreleased]
Add the following bullet point under the `[Unreleased]` section:
- `### Added` 
  - Interactive context injection via bottom chat bar with optimistic UI (`#23`)
  - Session control action buttons (Stop, Resume, Restart, Force Complete) with confirmation dialogs (`#23`)
  - Model & effort level selector modal to adjust thinking parameters (`#23`)
  - Toast notification system for enhanced feedback on control actions (`#23`)
