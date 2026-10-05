# Changelog

All notable changes to **Agent Manager** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **The Autonomous Feedback Flywheel & Expo Mobile Plan (`docs/hosting_and_expo_plan.md`)** (#102, #20, #16) — Elevated the cloud deployment and mobile hosting architecture plan to top priority, defining the closed-loop feedback flywheel: drop-in `<AgentFeedbackWidget />` and `POST /api/feedback/submit` in deployed apps (FitElo, Better Business Deal, Leanfolio, Agent Manager) that captures user context, device telemetry, and route data into structured GitHub Issues in `📋 Ready for Agent`, picked up autonomously by idle agents and verified on mobile via Expo.
- **Agent Lifecycle & Quick-Resume Operational Guide (`docs/agent_lifecycle_and_resume_guide.md`)** — Added a comprehensive operational guide detailing state preservation across worktrees, branches, database, and progress engine, with turnkey copy-paste prompts and a 5-step checklist for safely stopping and instantly resuming agent execution from a fresh chat session in under 30 seconds.
- **Metric-Driven Autonomous Progress Engine (`progress_engine.py`)** — Added dedicated background governor service and API endpoints (`GET /api/cron/progress-status`, `POST /api/cron/progress-now`) that continuously checks active execution sessions. When agents are running, it lets them proceed uninterrupted; when idle, it evaluates live Code Health and Manifesto compliance metrics, dynamically maps the highest-impact deficiency to its corresponding backlog issue (#100, #101, #39, #18, #90, etc.), and advances the task.
- **Code Quality, Readability, Simplicity & Testability Metrics Service (`code_quality_service.py`)** — Added dedicated AST-powered static analysis service and API endpoint (`GET /api/telemetry/code-health`) tracking lines of code per file, lines of code per function, bloated functions (> 40 LOC), root directory clutter, file distribution per folder, test-to-code ratio, unit vs. integration test counts, and composite code health score.
- **Enterprise Multi-Repo Swarm Roadmap & Backlog Seeding (#90–#101)** — Formulated and created 12 high-leverage issues on GitHub establishing the path to full multi-repo autonomous operations, spanning automated peer review (#90), ephemeral preview environments (#91), cross-repo semantic vector memory (#92), per-repo finops budgeting (#93), cross-repo task orchestration (#94), live USD cost telemetry (#95), multi-agent rebase conflict resolution (#96), Sentry bug self-healing (#97), SemVer release tagging (#98), Dependabot++ upgrades (#99), route controller refactoring (#100), and automated worktree pruning (#101).
- **Manifesto Compliance & Metric Evaluation Service (`manifesto_metrics.py`)** — Added a quantitative evaluation service and API endpoint (`GET /api/telemetry/manifesto-metrics`) that measures adherence across The Eight Pillars of the Agent Manager Manifesto (Observability, Isolation, Anti-Monolith, Process Decoupling, Cognitive Pipeline, Swarm Concurrency, Ubiquitous Command, and Accountability), computing a composite Manifesto Health Index.
- **Manifesto Metric Automated Test Suite (`test_manifesto_metrics.py`)** — Comprehensive unit and integration test suite asserting quantitative threshold criteria across all eight pillars and verifying endpoint integration.
- **The Agent Manager Manifesto (`MANIFESTO.md`)** — Established the foundational manifesto and architectural charter for Agent Manager. Synthesizes lessons from all completed and open issues into the 8 core pillars of autonomous agent engineering (Radical Observability, Sacred Isolation, Anti-Monolith Hygiene, Process Immortality, Cognitive Division of Labor, Autonomous Swarm Concurrency, Ubiquitous Command, Deterministic Accountability), 3-tier system topology, and multi-phase roadmap.
- **Decoupled Independent Agent Daemon Service** — Each autonomous agent now executes in its own dedicated, detached OS daemon service process (`agent_service.py` via `launch_independent_agent_service`). Agents run fully independent of the FastAPI web server lifecycle, allowing the web server and UI to be modified, updated, and restarted continuously without killing or interrupting running agents.
- **Auto-Reattaching Stream Tailer** — Added automatic process discovery and log tailer reattachment in FastAPI's `lifespan` startup hook. When the web server restarts or reloads, it discovers active agent PIDs via `is_process_alive`, resumes tailing stream JSON logs from the saved byte offset (`stream_log_offset`), and restores real-time WebSocket token streaming to the browser.
- **Atomic Single-Session Disk Persistence** — Added `save_single_session` in `storage.py` enabling independent agent daemon processes to update session state atomically in `data/sessions.json` without clobbering other concurrent agent sessions or web server writes.
- **Rich Markdown Rendering Component** — Added `MarkdownView.tsx` with full GitHub Flavored Markdown support including copyable code snippets, tables, blockquotes, and tasklist checkboxes.
- **One-Click Agent Restart Action** — Added `POST /api/issues/restart` with complete process tree termination (`taskkill /F /T`) and fresh instance instantiation.
- **Voice Issue Listener & Autonomous Task Spawner** — Added interactive voice recognition modal (`🎙️ Voice Issue`) with real-time speech transcription, AI-assisted issue structuring (acceptance criteria, overview, technical considerations), automatic GitHub Issue creation, Project Board #3 card placement, and 1-click autonomous agent assignment.
- **Voice Issue API Endpoint** — Added `/api/issues/voice-create` endpoint with intelligent repository inference from spoken text (`FitElo`, `Better Business Deal`, `Agent Manager`, `Leanfolio`, `F1 Frontend`) and automated agent spawner invocation.
- **Issue Command Center UI** — Replaced raw log terminal views with an executive Issue Command Center featuring direct issue control, repository filtering, search, status tabs, and 5-stage milestone trackers (`Worktree` ➔ `Code` ➔ `Tests` ➔ `Changelog` ➔ `PR`).
- **Algorithmic Supervisor & Agent Governance Engine** — Implemented deterministic supervisor module (`agent_manager/runners/supervisor.py`) enforcing automated GitHub takeover notices, project board status sync (`in_progress`, `in_review`), worktree boundary isolation, turn budget circuit breakers, and programmatic CHANGELOG verification.
- **Unified Issue Management API** — Consolidated endpoints into `/api/issues` (`/api/issues/start`, `/api/issues/pause`, `/api/issues/stop`, `/api/issues/sync`) for lightweight, direct issue orchestration.
- **Scheduler Pause & Resume Control** — Added manual and programmatic pause/resume controls for the autonomous cron dispatcher with UI toggle buttons in the Cron view, API endpoints (`/api/cron/pause`, `/api/cron/resume`), and persistent configuration.
- **Mandatory CHANGELOG.md Protocol & Directives** — Added Section 6 to `AGENTS.md` and injected changelog maintenance directives into agent takeover prompts, Stage 2/3 pipelines, webhooks, and interpretation services.
- **Dedicated Cron Runs View** — Added a dedicated `/cron` tab in the control plane dashboard to inspect execution history, per-repository evaluation summaries, and run statuses.
- **Direct GitHub Issue Creation** — Added an interactive modal in the Projects view to create issues directly into GitHub Project Board columns.
- **Multi-Repository Parallel Backlog Dispatching** — Re-architected task dispatcher to group project items per repository, preventing single-repo blocking and enabling independent agent concurrency.

### Changed
- **In-Review Local Agent Status Exemption** — Refactored scheduler, task dispatcher, and runner evaluator so that agents in `🔍 In Review` do not count as active running agents against worker capacity limits.
- **Immediate In-Progress Project Board Transition** — Agents taking over an issue immediately advance the Project Board card status to `⚡ In Progress` upon session initialization.

### Fixed
- **Projects View Board Loading & CSS Overflow** — Resolved scrolling and container clipping issues in the project view board interface.

---

## [0.1.0] - 2026-10-01

### Added
- Initial Antigravity Agent Manager control plane with local session orchestration, GitHub Project Board synchronization, and budget guardrails.
