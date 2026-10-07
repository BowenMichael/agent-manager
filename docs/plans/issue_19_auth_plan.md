# Implementation Plan: Issue #19 - Secure API Tokens for Control Plane

## 1. Architecture Overview
The goal is to secure the Control Plane (REST API and WebSocket) for public exposure (e.g., on Render) while maintaining a seamless developer experience via an opt-out mechanism. 
- **REST API Protection**: A new FastAPI `BaseHTTPMiddleware` will intercept all incoming requests. If `AUTH_ENABLED` is true, it will enforce a valid Bearer token for paths starting with `/api/agents` and `/api/settings`.
- **WebSocket Protection**: The `/ws/agents` endpoint will extract the `token` query parameter during the handshake and reject unauthorized connections before they are accepted.
- **Webhook Exemption**: The `/api/webhooks/github` route will bypass token validation because it relies on GitHub's HMAC signature mechanism.
- **Configuration**: Introduces `AUTH_ENABLED` (defaults to true) and `API_TOKEN` into `agent_manager/config.py`.

## 2. Target Files
- **`agent_manager/config.py`** (Modification): Add `AUTH_ENABLED` and `API_TOKEN` environment variables.
- **`agent_manager/api/auth.py`** (New File): Create the `APIAuthMiddleware` to handle Bearer token validation. Kept modular and well under the 250-line limit.
- **`agent_manager/server.py`** (Modification): Register the `APIAuthMiddleware` with the FastAPI app and modify the `/ws/agents` endpoint to check for the authentication token.
- **`tests/test_auth.py`** (New File): Create unit tests using `fastapi.testclient.TestClient` to verify 401 Unauthorized responses for invalid/missing tokens, successful access with valid tokens, and the `AUTH_ENABLED=false` bypass.
- **`CHANGELOG.md`** (Modification): Append the changes under the `[Unreleased]` section.

## 3. Step-by-Step Implementation Guide

**Step 1: Update Configuration**
- In `agent_manager/config.py`, add `AUTH_ENABLED` (reading from environment, defaulting to True) and `API_TOKEN` (reading from `API_TOKEN` or generating a fallback for local).

**Step 2: Create Authentication Middleware**
- In `agent_manager/api/auth.py`, implement `APIAuthMiddleware` inheriting from `BaseHTTPMiddleware`.
- Within the `dispatch` method, check if `config.AUTH_ENABLED` is active.
- If the path matches `/api/agents` or `/api/settings`, require the `Authorization: Bearer <TOKEN>` header.
- Return `401 Unauthorized` if the token is missing or invalid.

**Step 3: Update FastAPI Server**
- In `agent_manager/server.py`, import and add `APIAuthMiddleware` using `app.add_middleware()`.
- Update the `/ws/agents` endpoint signature to `async def websocket_agents(websocket: WebSocket, token: str = None):`.
- Implement early closure (`websocket.close(code=status.WS_1008_POLICY_VIOLATION)`) if authentication fails before `websocket.accept()`.

**Step 4: Create Unit Tests**
- In `tests/test_auth.py`, instantiate `TestClient(app)`.
- Write tests that patch `config.AUTH_ENABLED` and `config.API_TOKEN`.
- Test `GET /api/settings` without a header (expecting 401).
- Test `GET /api/settings` with a valid Bearer token (expecting 200).
- Test WebSocket handshake with and without a valid `token` query param.

**Step 5: Document Changes**
- Add an entry to `CHANGELOG.md` under `## [Unreleased] -> ### Security`.

## 4. Verification & Testing Criteria
- **REST API**: Ensure a `401 Unauthorized` response when making a request to `/api/agents` without an `Authorization` header. Ensure a `200 OK` response with a valid header.
- **WebSockets**: Ensure a connection attempt to `ws://.../ws/agents` without a valid `?token=` parameter fails the handshake.
- **Webhooks Exemption**: Ensure `/api/webhooks/github` can still be invoked without a Bearer token (verified via existing webhook tests).
- **Log Suppression**: All tests will be executed redirecting stdout/stderr to `.log` files to maintain clean output.

## 5. Updating CHANGELOG.md
A bullet point will be added:
```markdown
## [Unreleased]
### Security
- Implemented API Key / Bearer token authentication middleware for the REST API and WebSocket control plane, enabling secure public deployments (Issue #19).
```
