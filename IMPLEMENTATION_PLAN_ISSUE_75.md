# Implementation Plan: GitHub Issue #75 - React Frontend for Agent Manager

## 1. Architectural Overview
**Objective**: Build a modular React application to serve as the new graphical interface for the `agent-manager`, replacing or supplementing the existing vanilla HTML/JS static files.
- **Framework**: Vite + React + TypeScript. Vite provides a fast development server and optimized build process.
- **State Management & Data Fetching**: React Hooks and Context API for global state (e.g., active agents, WebSocket connection status).
- **Communication**: 
  - **REST API**: For static data, configurations, and launching new tasks (e.g., `/api/webhooks/...`).
  - **WebSockets**: Connect to `/ws/agents` for real-time streaming of agent logs, tool executions, and status updates.
- **Styling**: Standard CSS modules or Tailwind CSS (depending on existing preferences, but plain CSS modules keep it dependency-light).
- **Integration with Backend**: The Vite dev server will proxy API and WS requests to the FastAPI backend running on port 8000. For production, the React app will be built and its static files can optionally be served by FastAPI from `agent_manager/static`.

## 2. Target Files & Modular Breakdown
*STRICT ANTI-MONOLITH RULE: No file over 250 lines. Decompose logic into modular files.*

- **Project Root**:
  - `frontend/` (New directory for the React application)
- **Configuration & Setup**:
  - `frontend/package.json`
  - `frontend/tsconfig.json`
  - `frontend/vite.config.ts` (Configured to proxy `/api` and `/ws` to `http://localhost:8000`)
- **Types**:
  - `frontend/src/types/agent.ts` (Interfaces for AgentSession, Telemetry, etc.)
  - `frontend/src/types/api.ts` (Interfaces for API requests/responses)
- **Services (API & WebSocket)**:
  - `frontend/src/services/apiClient.ts` (Fetch wrapper for REST endpoints)
  - `frontend/src/services/wsClient.ts` (WebSocket connection manager with auto-reconnect)
- **State Management**:
  - `frontend/src/context/AgentContext.tsx` (Provides active agents and WebSocket state to the app)
- **Components**:
  - `frontend/src/App.tsx` (Main layout shell, max 100 lines)
  - `frontend/src/components/layout/Header.tsx` (Top navigation and stats)
  - `frontend/src/components/layout/Sidebar.tsx` (List of active/archived agents)
  - `frontend/src/components/dashboard/DashboardOverview.tsx` (High-level system metrics)
  - `frontend/src/components/stream/StreamViewer.tsx` (Live log and tool execution stream)
  - `frontend/src/components/stream/LogMessage.tsx` (Individual log entry component)
  - `frontend/src/components/control/LaunchAgentModal.tsx` (Form to launch new tasks/agents)

## 3. Step-by-Step Implementation Guide

**Stage 1: Initialization & Tooling Setup**
1. Create the React app structure using standard Vite templates inside a new `frontend/` folder.
2. Configure `vite.config.ts` to proxy requests starting with `/api` and `/ws` to the backend.
3. Define the strict TypeScript interfaces in `src/types/` based on the backend Pydantic models (e.g., Session state, telemetry data).

**Stage 2: Core Services & Context**
1. Implement `apiClient.ts` to handle common HTTP requests (GET, POST).
2. Implement `wsClient.ts` to manage the WebSocket connection to `/ws/agents`. It should parse incoming JSON messages and dispatch events.
3. Create `AgentContext.tsx` to hold the global state of sessions (active, archived) and update this state dynamically when the WebSocket receives data.

**Stage 3: UI Layout & Shell**
1. Build the main layout (`App.tsx`, `Header.tsx`, `Sidebar.tsx`).
2. The Sidebar should list agent sessions grouped by status (Running, Archived), fetching initial data via API or WebSocket initialization.

**Stage 4: Stream Viewer & Dashboard**
1. Implement `StreamViewer.tsx` to display the real-time transcript of the selected agent. This component must handle auto-scrolling as new logs arrive.
2. Implement `DashboardOverview.tsx` to show aggregate telemetry (total tokens, active agents).

**Stage 5: Control Panel & Modals**
1. Create `LaunchAgentModal.tsx` to allow users to trigger a new agent task by submitting form data to the corresponding API endpoint.

## 4. Verification & Testing Criteria

- **Build Validation**:
  - Run `cd frontend && npm run build > build_run.log 2>&1`.
  - Ensure the exit code is 0. Delete the log on success.
- **Type Checking & Linting**:
  - Run `cd frontend && npx tsc --noEmit > tsc_run.log 2>&1`.
  - Ensure the exit code is 0. Delete the log on success.
- **Functionality Verification**:
  - The React frontend successfully connects to the backend WebSocket (`/ws/agents`).
  - Active sessions are accurately displayed in the sidebar.
  - New agent events render in real-time in the StreamViewer without requiring a page refresh.
