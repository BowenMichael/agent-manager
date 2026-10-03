# 🤖 Agent-Driven Development Starter Blueprint

A tech-stack agnostic starter template for orchestrating autonomous AI pair-programming agents using **GitHub Projects (Jira-style Kanban)** and **Model Context Protocol (MCP)**.

Works seamlessly with any language or framework: **Next.js, React, Vue, Python (FastAPI/Django), Go, Rust, Ruby, Node, etc.**

---

## 📦 What's Included

- **`.github/ISSUE_TEMPLATE/agent_task.md`**: Pre-configured task template enforcing objectives, acceptance criteria, and visual demo verification.
- **`.github/pull_request_template.md`**: Structured PR template with sections for video demo embeds, before/after screenshots, test logs, and reviewer checklists.
- **`.github/workflows/agent-task-dispatcher.yml`**: GitHub Actions event runner that auto-acknowledges tasks and supports external webhook forwarding.
- **`AGENTS.md`**: Production-grade agent rulebook enforcing:
  - **Git Worktree Isolation**: Agents work strictly in `.worktrees/issue-<#>` to never touch your active editor.
  - **Token & Budget Guardrail**: Mandatory pause and insights report if a task reaches 15 turns.
  - **Anti-Duplication**: Board-status driven task pickup and immediate takeover comments.
- **`mcp_config.template.json`**: Pre-configured MCP configuration for GitHub, Vercel, and deployment integrations.
- **`setup.js`**: One-click initialization script to create all GitHub labels in any new repository.

---

## 🚀 Quickstart: Using This Template for Any New Repo

### Step 1: Copy Template Files into Your Repo
Copy the `.github/`, `AGENTS.md`, and `mcp_config.template.json` files to the root of your project:
```bash
cp -r .github/ /path/to/your-new-project/
cp AGENTS.md /path/to/your-new-project/
cp mcp_config.template.json /path/to/your-new-project/
```

### Step 2: Run One-Click Label Setup
Run the setup script with your repository name and GitHub Personal Access Token (PAT):
```bash
node setup.js <your-github-username>/<your-repo-name> <your-github-token>
```
This automatically registers the workflow labels:
- 🟢 `agent:ready`
- 🟡 `agent:in-progress`
- 🟠 `agent:needs-approval`
- 🟣 `agent:review`

### Step 3: Configure MCP in Antigravity
Copy the contents of `mcp_config.template.json` into your global config (`~/.gemini/config/mcp_config.json`) and insert your GitHub PAT.

### Step 4: Launch the Background Scheduler
In Antigravity chat, trigger your recurring background daemon:
```
/schedule CronExpression="*/3 * * * *" Prompt="Check repository <owner>/<repo> for items with Status '📋 Ready for Agent'..."
```

---

## 🔄 Daily Workflow
1. **Create an Issue** using the `[TASK]` template on GitHub.
2. **Move to '📋 Ready for Agent'** on your Kanban board.
3. **Agent Picks Up**: Automatically creates an isolated `.worktrees/issue-<#>`, posts a takeover comment, writes code, and runs tests.
4. **Review & Approve**: The agent opens a PR with an attached video walkthrough and screenshots, moving the card to `🔍 In Review`.
