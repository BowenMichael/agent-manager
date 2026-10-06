# Production Deployment & Operations Guide

This guide walks through deploying the Agent Manager backend on [Render](https://render.com) and building the cross-platform frontend app using [Expo Application Services (EAS)](https://expo.dev/eas).

---

## 1. Architecture Summary

Agent Manager utilizes a decoupled cloud architecture:
- **FastAPI Web Service**: Ingests GitHub webhooks, manages agent processes, and serves real-time WebSocket streams.
- **Render PostgreSQL**: Stores persistent session metadata, execution logs, and transcripts.
- **Render Key-Value (Redis)**: Manages pub/sub events and asynchronous agent job queues.
- **Expo Client**: Web, iOS, and Android control plane communicating over HTTPS REST and WSS WebSockets.

---

## 2. Render Cloud Setup

### 2.1 Provision Managed PostgreSQL & Redis
1. In the Render Dashboard, create a **PostgreSQL** instance:
   - Name: `agent-manager-db`
   - Database & User: `agent_manager`
   - Plan: Free or Starter
   - Copy the **Internal Database URL** for service configuration.
2. Create a **Redis** instance:
   - Name: `agent-manager-redis`
   - Plan: Starter
   - Copy the **Internal Redis URL**.

### 2.2 Create the FastAPI Web Service
1. Click **New +** -> **Web Service** and connect the `agent-manager` repository.
2. Configure settings:
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn agent_manager.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Starter or higher (persistent CPU recommended for running agent workflows).

---

## 3. Environment Variables & Secrets

Configure the following environment variables under **Environment** in your Render Web Service:

| Variable | Description | Example / Source |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL connection string | Copied from Render PostgreSQL internal URL |
| `REDIS_URL` | Redis connection string | Copied from Render Redis internal URL |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | GitHub PAT with repo & project scopes | Created in GitHub Developer Settings |
| `GITHUB_WEBHOOK_SECRET` | Secret key used to verify HMAC signatures | Random 32+ character hex string |
| `ANTIGRAVITY_API_KEY` | Key for Google Antigravity SDK | Antigravity developer portal / config |
| `CORS_ORIGINS` | Permitted client origins | `https://your-custom-domain.com,https://localhost:8081` |

---

## 4. Custom Domains & Automated SSL

1. Navigate to **Settings > Custom Domains** in your Render Web Service.
2. Add your custom domain (e.g., `api.agent-manager.dev`).
3. Point your DNS provider's records:
   - For subdomains: Add a `CNAME` record pointing to your Render service address (e.g. `agent-manager.onrender.com`).
   - For root domains: Add `ANAME` or `ALIAS` records pointing to Render's IP addresses.
4. Render automatically provisions and renews Let's Encrypt TLS/SSL certificates once DNS propagates.

---

## 5. WebSockets Behind Proxies & Load Balancers

Agent Manager uses WebSockets (`/ws/agents`) for real-time telemetry streaming:
- **Keep-Alives**: Configure heartbeat pings (every 30s) on both client and server to prevent Render's reverse proxy idle timeout (typically 100 seconds).
- **Sticky Sessions / Single Instance**: If scaling horizontally, ensure Redis pub/sub adapter is enabled to broadcast agent updates across all service instances.
- **WSS Protocol**: Always connect using `wss://` in production to comply with SSL termination at the Render edge proxy.

---

## 6. Expo EAS Build & Distribution

The mobile and web client is built using Expo (SDK 51+).

### 6.1 Prerequisites
```bash
npm install -g eas-cli
eas login
```

### 6.2 Configure `eas.json`
Verify build profiles in `frontend/eas.json`:
```json
{
  "cli": { "version": ">= 9.0.0" },
  "build": {
    "development": { "developmentClient": true, "distribution": "internal" },
    "preview": { "distribution": "internal", "android": { "buildType": "apk" } },
    "production": {}
  }
}
```

### 6.3 Android Standalone APK Build
To generate a standalone APK for testing:
```bash
cd frontend
eas build --platform android --profile preview
```
Download the resulting `.apk` file from the link in the terminal upon build completion.

### 6.4 iOS TestFlight Distribution
To build and submit directly to Apple TestFlight:
```bash
cd frontend
eas build --platform ios --profile production --auto-submit
```
Ensure Apple Developer account credentials and App Store Connect API keys are configured when prompted.
