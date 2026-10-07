# Implementation Plan: Issue #21 - Real-Time Session Feed & WebSocket Client

## 1. Architecture Overview
The current client in `frontend/` acts as the control plane UI. We will transition from the existing basic `AgentContext` to a scalable **Zustand** state management store to synchronize agent session states via the WebSocket (`/ws/agents`). This fulfills the requirement for an auto-reconnecting real-time state store and sets the foundation for the cross-platform application UI.

Key modifications:
- Introduce **Zustand** as the primary state store for active and historical sessions.
- Upgrade the `AgentWebSocketClient` to feature **exponential backoff** for auto-reconnection.
- Build modular UI components for the **Session List** and **Status Pills** to display live data.
- Integrate a **Connection Banner** that surfaces offline/disconnected states to the user.

## 2. Target Files
*(All files will be kept under 250 lines to adhere to the Anti-Monolith Rule)*

1. `frontend/src/store/useAgentStore.ts` (New)
2. `frontend/src/services/wsClient.ts` (Modify)
3. `frontend/src/components/dashboard/StatusPill.tsx` (New)
4. `frontend/src/components/dashboard/SessionList.tsx` (New)
5. `frontend/src/components/layout/ConnectionBanner.tsx` (New)
6. `frontend/src/components/dashboard/DashboardOverview.tsx` (Modify)
7. `CHANGELOG.md` (Modify)

## 3. Step-by-Step Implementation Guide

**Step 1: Install Dependencies**
- Run `npm install zustand` in the `frontend` directory.

**Step 2: Build the Zustand Store (`useAgentStore.ts`)**
- Create a store holding `agents` (Array of `AgentSessionInfo`), `isConnected`, `selectedSessionId`.
- Add actions: `setAgents`, `updateAgent` (optimistic update), `setConnectionStatus`, `selectSession`.

**Step 3: Enhance WebSocket Client (`wsClient.ts`)**
- Refactor `scheduleReconnect()` to track reconnection attempts and apply exponential backoff.
- Example: `delay = Math.min(1000 * Math.pow(2, attempts), 30000)`.

**Step 4: Create UI Components**
- **StatusPill**: Accept an `AgentStatus` prop. Map `RUNNING`, `PAUSED`, `IN_REVIEW`, `COMPLETED`, `STOPPED`, and `FAILED` to specific background and text colors (using inline styles or Tailwind/CSS if configured).
- **SessionList**: Connect to the Zustand store (`useAgentStore(state => state.agents)`). Map over agents to display cards/rows including the `StatusPill`, session title, and metadata. Implement a pull-to-refresh style action triggering a REST fetch as a fallback.
- **ConnectionBanner**: A fixed banner at the top of the app reading `isConnected` from Zustand, displaying a warning when disconnected.

**Step 5: Integration & Cleanup**
- Inject the `AgentWebSocketClient` in a root layout or main `App.tsx` component, binding it to the Zustand store's actions.
- Replace any usage of `AgentContext` with `useAgentStore` inside `DashboardOverview.tsx`.
- Delete `AgentContext.tsx` if fully deprecated.

## 4. Verification & Testing Criteria
- **WebSocket Reconnection**: Force disconnect the server (stop FastAPI) and verify the client attempts to reconnect with increasing delays (1s, 2s, 4s, etc., max 30s).
- **State Integrity**: Spawn a new agent; verify it appears in the list instantly without a hard refresh.
- **Visuals**: The offline banner appears correctly when disconnected and hides when reconnected. The Status Pills render the correct colors for the different states.
- **Linting/Typecheck**: Run `npm run lint` and `npm run build` in `frontend/` to ensure no errors. Ensure output logs are suppressed in PowerShell per rules.

## 5. Updating CHANGELOG.md
- Add a bullet point under the `## [Unreleased]` section categorized as `### Added`:
  - `Added Zustand state management and auto-reconnecting WebSocket client with exponential backoff for live session tracking (#21).`
