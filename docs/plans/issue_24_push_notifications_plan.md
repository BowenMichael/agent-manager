# Implementation Plan: Issue #24 [EXPO]: Add Push Notifications for Task Milestones & Guardrail Alerts

## 1. Architecture Overview
To support Expo Push Notifications (`expo-notifications`), we need a full-stack integration bridging our FastAPI backend with the Expo application.

### Backend Push Architecture
1. **Device Registration API**: An endpoint (`POST /api/notifications/register`) that receives the `ExpoPushToken` from mobile clients and stores it (initially in-memory or in the session storage).
2. **Push Service Wrapper**: A dedicated module (`agent_manager/services/expo_push.py`) that uses `httpx` to send batched or single notifications to `https://exp.host/--/api/v2/push/send`.
3. **Event Triggers**: The `AgentRunnerManager` in `runner.py` will emit events when a session transitions to `IN_REVIEW`, `PAUSED` (due to guardrails), or `FAILED`. These events will trigger the push service.

### Frontend (Expo Client) Architecture
1. **Permission Request Flow**: An Expo hook (`usePushNotifications.ts`) utilizing `expo-notifications` and `expo-device` to request notification permissions from the user.
2. **Token Registration**: Upon receiving the token, the client sends it to the backend `/api/notifications/register`.
3. **Deep Linking / Routing**: Utilizing `expo-router`, incoming notification interactions are mapped to specific session detail routes (e.g., `/(sessions)/[id]`). Since the Expo app codebase is pending generation under `apps/mobile`, we will scaffold the necessary React Native client code required to satisfy these acceptance criteria in a generic client structure, or inject it directly if an Expo client workspace is scaffolded.

---

## 2. Target Files

**Backend:**
1. `agent_manager/services/expo_push.py` (NEW - ~100 lines)
   - Expo Push API wrapper logic, formatting payloads, error handling.
2. `agent_manager/api/routes/notifications.py` (NEW - ~50 lines)
   - `POST /register` endpoint to receive tokens.
3. `agent_manager/server.py` (EDIT)
   - Include the `notifications.py` router.
4. `agent_manager/runner.py` (EDIT)
   - Import the `expo_push` service and trigger notifications on `IN_REVIEW`, `PAUSED`, `FAILED` state transitions.

**Frontend (Expo Client under `apps/mobile/`):**
1. `apps/mobile/src/hooks/usePushNotifications.ts` (NEW - ~80 lines)
   - Permission logic, token fetching, listener setup.
2. `apps/mobile/src/app/_layout.tsx` (NEW/EDIT - ~50 lines)
   - Setup notification handler (`setNotificationHandler`).
3. `apps/mobile/src/services/apiClient.ts` (EDIT)
   - Add method to register push token with backend.

*(All files are kept well below the 250-line monolithic limit).*

---

## 3. Step-by-Step Implementation Guide

### Phase 1: Backend Services & API
1. **Create Expo Push Wrapper**:
   - Write `agent_manager/services/expo_push.py` using `httpx.AsyncClient` to send push payloads.
   - Define payload schema (to, title, body, data).
2. **Implement Registration Endpoint**:
   - Create `agent_manager/api/routes/notifications.py` with `POST /register` to save device push tokens into a global registry.
3. **Wire Router**:
   - Register the router in `agent_manager/server.py`.
4. **Trigger Events in Runner**:
   - Modify `agent_manager/runner.py` where states transition (e.g., inside `_run_loop` or explicit status setters).
   - If `status == AgentStatus.IN_REVIEW`, trigger: "Agent {id} is ready for review."
   - If `status == AgentStatus.PAUSED`, trigger: "Agent {id} hit a guardrail limit."
   - If `status == AgentStatus.FAILED`, trigger: "Agent {id} encountered an error."

### Phase 2: Expo Client Scaffold & Permissions
1. **Scaffold Expo Configuration**:
   - If `apps/mobile` does not exist, scaffold a minimal layout or provide the exact files so they are ready for compilation.
2. **Implement Notification Hook**:
   - Write `usePushNotifications.ts` to request permissions on mount using `Notifications.requestPermissionsAsync()`.
   - Retrieve `ExpoPushToken` and dispatch to backend.
3. **Configure Foreground Handlers & Routing**:
   - In the root layout, add `Notifications.setNotificationHandler` so alerts show in the foreground.
   - Attach listeners (`addNotificationResponseReceivedListener`) to use `expo-router`'s `router.push(url)` reading from `notification.request.content.data.url`.

---

## 4. Verification & Testing Criteria

- **Unit/API Tests**:
  - `POST /api/notifications/register` returns `200 OK` and saves token.
  - Mock the `httpx.AsyncClient` in `expo_push.py` to assert correct payload construction and headers.
- **Integration Validation**:
  - Spawn an agent and force a pause (e.g. token threshold mock). Verify `expo_push.send` is invoked with the stored token.
- **Client Flow Validation**:
  - Ensure the client hook attempts to fetch a token and handles `Device.isDevice` correctly.

---

## 5. Updating CHANGELOG.md
Under the `## [Unreleased]` section, the following entry will be appended:
```markdown
### Added
- Backend integration for Expo Push Notifications to alert users on key agent milestones (`IN_REVIEW`, `PAUSED`, `FAILED`) (#24).
- Device registration endpoint `/api/notifications/register` for client Expo push tokens (#24).
- Client-side push permission hooks and deep-link routing configuration for the upcoming Expo mobile app (#24).
```
