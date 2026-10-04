# Changelog

All notable changes to **Agent Manager** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
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
