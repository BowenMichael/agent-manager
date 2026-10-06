# Implementation Plan: Issue #26

## 1. Architecture Overview
The Agent Manager is transitioning to a hybrid cloud and mobile control plane architecture. The deployment strategy focuses on two main platforms:
- **Render**: Hosts the backend services. The topology includes a FastAPI Web Service, managed PostgreSQL for persistent state, Redis for real-time pub/sub and job queues, and an optional background worker. This involves handling webhook ingest, secure WebSockets behind proxies, and setting up environment variables.
- **Expo**: Handles the client layer (Web, iOS, Android). Expo Application Services (EAS) will be used to build and distribute the app to TestFlight, Google Play, or standalone APKs.

This guide will document the necessary operational steps to deploy these components in production successfully.

## 2. Target Files
- **`docs/deployment.md`** (New File): The comprehensive guide for deploying Agent Manager on Render and Expo. To comply with the anti-monolith rule (keep files under 250 lines), the guide will be written concisely. If it risks exceeding 250 lines, it will be split logically (e.g., `deployment-backend.md` and `deployment-mobile.md`), but a single focused file is the initial target.
- **`README.md`** (Modification): Will be updated to include a prominent link to the new deployment guide, likely in a new "Deployment" or "Documentation" section.
- **`CHANGELOG.md`** (Modification): Will be updated under `[Unreleased]` with a summary of the new documentation provided for this issue.

## 3. Step-by-Step Implementation Guide

**Step 1: Draft the Deployment Guide**
- Create `docs/deployment.md`.
- **Render Backend Setup**: Document PostgreSQL and Redis provisioning. Document creating the Web Service (Python/Docker) and configuring environment variables (`DATABASE_URL`, `REDIS_URL`, `GITHUB_PERSONAL_ACCESS_TOKEN`, `GITHUB_WEBHOOK_SECRET`).
- **Domain & SSL**: Document custom domain binding and automated SSL certificate configuration on Render.
- **WebSockets**: Provide guidelines for WebSocket connectivity behind Render's load balancers.
- **Expo EAS Build**: Document the Expo setup, including `eas.json` configuration, running `eas build` for iOS and Android, and publishing to TestFlight and APK distribution.

**Step 2: Update README.md**
- Find an appropriate section (after Quick Start or Configuration).
- Insert a link to `docs/deployment.md` for users looking to deploy to production.

**Step 3: Update CHANGELOG.md**
- Append a bullet point under the `### Added` section in the `[Unreleased]` block describing the creation of the operations and deployment guide, referencing `(#26)`.

## 4. Verification & Testing Criteria
- [ ] `docs/deployment.md` is created and accurately reflects the architecture described in `docs/hosting_and_expo_plan.md`.
- [ ] The markdown file is correctly formatted, easily readable, and under 250 lines.
- [ ] `README.md` includes a working relative markdown link to the deployment guide.
- [ ] No monolithic files are created, and all rules regarding file reads/writes are followed.

## 5. Updating CHANGELOG.md
- Ensure `CHANGELOG.md` has an entry structured like: `* Added comprehensive deployment and operations guide for Render and Expo EAS (#26)`.
