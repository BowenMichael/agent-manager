import asyncio
import logging
import httpx
from typing import Optional, Set, Dict

from agent_manager import config
from agent_manager.config import (
    GITHUB_PERSONAL_ACCESS_TOKEN, PROJECT_BOARD_ID, PROJECT_BOARD_IDS,
    DEFAULT_REPO, POLL_INTERVAL_SECONDS
)
from agent_manager.models import SpawnRequest, AgentStatus
from agent_manager.runner import AgentRunnerManager
from agent_manager.formatters.comments import is_agent_comment

logger = logging.getLogger("agent_manager.poller")

# Project Board V2 Field and Option IDs (F1 Viewer Sprint Board)
STATUS_FIELD_ID = "PVTSSF_lAHOAgkA3s4BlmhhzhkSuu0"
STATUS_NAMES = {
    "backlog": "📥 Backlog",
    "ready": "📋 Ready for Agent",
    "in_progress": "⚡ In Progress",
    "in_review": "🔍 In Review",
    "done": "✅ Done",
}
STATUS_OPTIONS = {
    "backlog": "3abe26ce",      # 📥 Backlog
    "ready": "8b88d8d3",        # 📋 Ready for Agent
    "in_progress": "0855f60f",  # ⚡ In Progress
    "in_review": "14cfb9b7",    # 🔍 In Review
    "done": "b167c286"          # ✅ Done
}

def is_empty_or_template_only(body: Optional[str]) -> bool:
    """Detects if an issue body contains only template boilerplate or empty comments."""
    if not body or not body.strip():
        return True
    import re
    # Strip markdown comments <!-- ... -->
    cleaned = re.sub(r'<!--.*?-->', '', body, flags=re.DOTALL)
    # Strip markdown headers, checkboxes, and standard template section titles
    cleaned = re.sub(r'#+\s*', '', cleaned)
    cleaned = re.sub(r'-\s*\[\s*\]\s*Criterion\s*\d+', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'-\s*\[\s*\]\s*', '', cleaned)
    cleaned = re.sub(r'(Objective|Acceptance Criteria|Requirements|Description|Context):?', '', cleaned, flags=re.IGNORECASE)
    return len(cleaned.strip()) < 15

class LocalGitWatcher:
    """
    Local Git & Project Board Synchronizer.
    Enables 100% local agent dispatching without opening external ports or tunnels.
    Moves board status directly without adding tags/labels to issues.
    Ensures chats stay open until manually moved into 'Done'.
    Detects re-queued tasks and checks for new comments or modifications.
    """
    _instance: Optional["LocalGitWatcher"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_watcher()
        return cls._instance

    def _init_watcher(self):
        self.runner = AgentRunnerManager()
        self.active_issues: Set[str] = set()
        self.item_id_map: Dict[str, str] = {}  # "owner/repo#num" -> project_item_id
        self.item_project_map: Dict[str, str] = {}  # project_item_id -> project_id
        self._board_fields: Dict[str, dict] = {}  # project_id -> {"field_id":..., "options": {key: option_id}}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._poll_loop())
            logger.info("Local Git Watcher started (polling interval: %ss)", POLL_INTERVAL_SECONDS)

    def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Local Git Watcher stopped")

    async def _poll_loop(self):
        while self._running:
            try:
                if GITHUB_PERSONAL_ACCESS_TOKEN:
                    for board_id in PROJECT_BOARD_IDS:
                        await self._check_project_board(board_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in Git watcher poll: %s", e)

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _resolve_board_fields(self, project_id: str) -> Optional[dict]:
        if project_id in self._board_fields:
            return self._board_fields[project_id]
        query = """
        query($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              fields(first: 30) {
                nodes {
                  ... on ProjectV2SingleSelectField { id name options { id name } }
                }
              }
            }
          }
        }
        """
        headers = {"Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}", "Content-Type": "application/json", "User-Agent": "AgentManagerLocal/1.0"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post("https://api.github.com/graphql", json={"query": query, "variables": {"projectId": project_id}}, headers=headers)
        nodes = (resp.json().get("data", {}).get("node", {}) or {}).get("fields", {}).get("nodes", [])
        for f in nodes:
            if f and f.get("name") == "Status":
                opts = {}
                for key, name in STATUS_NAMES.items():
                    for o in f.get("options", []):
                        if o["name"] == name:
                            opts[key] = o["id"]
                self._board_fields[project_id] = {"field_id": f["id"], "options": opts}
                return self._board_fields[project_id]
        logger.warning("No Status field found on project %s", project_id)
        return None

    async def update_item_status(self, item_id: str, status_key: str, project_id: Optional[str] = None) -> bool:
        """Updates the status column directly on GitHub Project Board V2 without touching issue tags."""
        pid = project_id or self.item_project_map.get(item_id, PROJECT_BOARD_ID)
        board = await self._resolve_board_fields(pid)
        if not board or status_key not in board["options"]:
            logger.warning("Cannot resolve status '%s' on project %s", status_key, project_id)
            return False
        option_id = board["options"][status_key]
        mutation = """
        mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
          updateProjectV2ItemFieldValue(
            input: {
              projectId: $projectId
              itemId: $itemId
              fieldId: $fieldId
              value: { singleSelectOptionId: $optionId }
            }
          ) {
            projectV2Item { id }
          }
        }
        """
        headers = {
            "Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "AgentManagerLocal/1.0"
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.github.com/graphql",
                    json={
                        "query": mutation,
                        "variables": {
                            "projectId": pid,
                            "itemId": item_id,
                            "fieldId": board["field_id"],
                            "optionId": option_id
                        }
                    },
                    headers=headers
                )
                if resp.status_code != 200:
                    logger.error("GraphQL mutation failed with status %d: %s", resp.status_code, resp.text)
                    return False
                res_data = resp.json()
                if "errors" in res_data:
                    logger.error("GraphQL mutation returned errors: %s", res_data["errors"])
                    return False
                return bool(res_data.get("data", {}).get("updateProjectV2ItemFieldValue"))
        except Exception as e:
            logger.error("Failed to update item status: %s", e)
            return False

    async def update_issue_status(self, repo: str, issue_number: int, status_key: str) -> bool:
        """Updates the status of an issue on the Project Board by its repo and issue number."""
        key = f"{repo}#{issue_number}"
        item_id = self.item_id_map.get(key)
        if not item_id:
            # Refresh project boards to resolve item_id if not currently cached
            for b in PROJECT_BOARD_IDS:
                await self._check_project_board(b)
                if key in self.item_id_map:
                    item_id = self.item_id_map[key]
                    break
        if item_id:
            return await self.update_item_status(item_id, status_key)
        logger.warning("Could not find project board item for %s", key)
        return False

    async def _check_project_board(self, project_id: str = PROJECT_BOARD_ID):
        query = """
        query($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 30) {
                nodes {
                  id
                  fieldValues(first: 10) {
                    nodes {
                      ... on ProjectV2ItemFieldSingleSelectValue {
                        name
                        optionId
                        field { ... on ProjectV2SingleSelectField { name } }
                      }
                    }
                  }
                  content {
                    ... on Issue {
                      id
                      number
                      title
                      body
                      state
                      updatedAt
                      comments(last: 10) {
                        nodes {
                          id
                          author { login }
                          body
                          createdAt
                        }
                      }
                      repository { nameWithOwner }
                    }
                  }
                }
              }
            }
          }
        }
        """
        headers = {
            "Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "AgentManagerLocal/1.0"
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.github.com/graphql",
                json={"query": query, "variables": {"projectId": project_id}},
                headers=headers
            )
            if resp.status_code != 200:
                logger.warning("GraphQL request failed with status: %s", resp.status_code)
                return

            data = resp.json()
            items = data.get("data", {}).get("node", {}).get("items", {}).get("nodes", [])

            for item in items:
                status_name = None
                option_id = None
                for fv in item.get("fieldValues", {}).get("nodes", []):
                    if fv.get("field", {}).get("name") == "Status":
                        status_name = fv.get("name")
                        option_id = fv.get("optionId")
                        break

                content = item.get("content")
                if not content or "number" not in content:
                    continue

                issue_num = content["number"]
                title = content["title"]
                body = content.get("body") or ""
                issue_state = content.get("state", "OPEN")
                repo = content.get("repository", {}).get("nameWithOwner", DEFAULT_REPO)
                comments = content.get("comments", {}).get("nodes", [])
                issue_key = f"{repo}#{issue_num}"
                self.item_id_map[issue_key] = item["id"]
                self.item_project_map[item["id"]] = project_id

                # 1. LIFECYCLE: Completed if issue closed on GitHub or card moved to Done
                if issue_state == "CLOSED" or status_name == STATUS_NAMES["done"]:
                    if issue_state == "CLOSED" and status_name != STATUS_NAMES["done"]:
                        await self.update_item_status(item["id"], "done")
                        logger.info("Issue #%s detected as CLOSED on GitHub. Moved card to '✅ Done' on Project Board.", issue_num)
                    for s in self.runner.list_sessions():
                        if s.issue_number == issue_num and s.repo == repo and s.status != AgentStatus.COMPLETED:
                            logger.info("Issue #%s detected as closed/done. Formally completing and archiving session %s", issue_num, s.session_id)
                            await self.runner.complete_agent(s.session_id, reason="Issue closed/merged on GitHub")
                    self.active_issues.discard(issue_key)
                    continue

                # 2. ACTIVE COMMENT POLLING: Check for new user comments on active/in-review sessions
                active_session = next(
                    (s for s in reversed(self.runner.list_sessions()) if s.issue_number == issue_num and s.repo == repo and s.status != AgentStatus.COMPLETED),
                    None
                )

                if active_session:
                    seen_ids = {str(x) for x in active_session.seen_comment_ids}
                    new_comments = [
                        c for c in comments
                        if str(c.get("id")) not in seen_ids
                        and not is_agent_comment(c.get("body"))
                    ]

                    if new_comments:
                        update_sections = ["### New Comment(s) from User on GitHub:"]
                        for nc in new_comments:
                            author = nc.get("author", {}).get("login", "User")
                            update_sections.append(f"- **@{author}**: {nc.get('body', '').strip()}")
                            active_session.seen_comment_ids.append(str(nc.get("id")))

                        feedback_text = "\n\n".join(update_sections)
                        logger.info(
                            "Issue #%s has %d new user comment(s). Injecting continuation context into session %s.",
                            issue_num, len(new_comments), active_session.session_id
                        )
                        active_session.last_issue_body = body
                        self.runner._save()

                        # Move status on Project Board to In Progress per AGENTS.md rule
                        if status_name != STATUS_NAMES["in_progress"]:
                            await self.update_item_status(item["id"], "in_progress")
                            logger.info("Updated Issue #%s Project Board status to '⚡ In Progress' due to new comment", issue_num)

                        continuation_prompt = (
                            f"A user commented on GitHub Issue #{issue_num} ({repo}):\n\n"
                            f"{feedback_text}\n\n"
                            f"**Operational Guidelines**:\n"
                            f"- Address the user's question or feedback directly.\n"
                            f"- Follow AGENTS.md rules: do not add issue labels, keep status transitions purely on the Project Board.\n"
                            f"- If code changes or tests are needed, execute them in your worktree.\n"
                            f"- When finished, summarize your findings or post your response."
                        )
                        await self.runner.add_context(active_session.session_id, continuation_prompt)
                        continue

                # 3. AUTO-SYNC: If session is IN_REVIEW and no new comments, ensure Project Board is marked In Review
                if active_session and active_session.status == AgentStatus.IN_REVIEW:
                    if status_name != STATUS_NAMES["in_review"]:
                        await self.update_item_status(item["id"], "in_review")
                        logger.info("Updated Issue #%s Project Board status to '🔍 In Review'", issue_num)

                # 4. RE-QUEUE & NEW ISSUE: Status is '📋 Ready for Agent'
                if status_name == STATUS_NAMES["ready"]:
                    if active_session:
                        # User dragged card back into Ready for Agent
                        body_changed = (
                            active_session.last_issue_body is not None and
                            body.strip() != active_session.last_issue_body.strip()
                        )
                        logger.info("Issue #%s was moved back to Ready for Agent. Triggering continuation pass.", issue_num)
                        active_session.last_issue_body = body
                        self.runner._save()

                        await self.update_item_status(item["id"], "in_progress")
                        logger.info("Updated Issue #%s Project Board status to '⚡ In Progress'", issue_num)

                        prompt_text = f"Issue #{issue_num} has been moved back into Ready for Agent."
                        if body_changed:
                            prompt_text += f"\n\n### Updated Issue Description:\n{body.strip()}"

                        continuation_prompt = (
                            f"{prompt_text}\n\n"
                            f"Please review the work completed in the worktree, test existing features, and continue working on any remaining requirements."
                        )
                        await self.runner.add_context(active_session.session_id, continuation_prompt)
                        continue

                    else:
                        # Brand new agent task spawn
                        active_sessions = [
                            s for s in self.runner.list_sessions()
                            if s.issue_number == issue_num and s.repo == repo and s.status in [AgentStatus.RUNNING, AgentStatus.INITIALIZING, AgentStatus.PAUSED]
                        ]
                        if not active_sessions and issue_key not in self.active_issues:
                            logger.info("Found new issue #%s in Ready for Agent. Moving status to In Progress on Project Board...", issue_num)
                            self.active_issues.add(issue_key)

                            await self.update_item_status(item["id"], "in_progress")
                            logger.info("Updated Issue #%s Project Board status to '⚡ In Progress'", issue_num)

                            prompt_body = body
                            if is_empty_or_template_only(body):
                                logger.warning(
                                    "Issue #%s has empty/placeholder description. Adding guidance note to prevent blind exploratory loops.",
                                    issue_num
                                )
                                prompt_body = (
                                    f"{body}\n\n"
                                    f"⚠️ **Note on Scope**: The issue description contains template placeholders. "
                                    f"Focus strictly on achieving the objective specified in the title: '{title}'. "
                                    f"Do not guess non-existent criteria."
                                )

                            prompt = (
                                f"You have been assigned to GitHub Issue #{issue_num} in {repo}.\n\n"
                                f"**Title**: {title}\n\n"
                                f"**Requirements / Description**:\n{prompt_body}\n\n"
                                f"**Operational Guidelines & Efficiency Rules**:\n"
                                f"- Work inside the designated branch and isolated worktree .worktrees/issue-{issue_num}.\n"
                                f"- SEARCH FIRST: Always use grep_search to find exact symbol, function, or line locations BEFORE calling view_file.\n"
                                f"- SLICE READING ONLY: When calling view_file, ALWAYS supply StartLine and EndLine (max 100 lines at once). NEVER view entire large files over 200 lines.\n"
                                f"- NEVER RE-READ: Do NOT call view_file on the same file or line range twice in a row. Rely on context and proceed directly to code edits or tests.\n"
                                f"- ANTI-MONOLITH RULE: Never create monolithic files over 250 lines. Decompose logic into modular, single-responsibility files (models, services, utils, components). When modifying large files (>300 lines), extract new functions into separate helper files.\n"
                                f"{('- CIRCUIT BREAKER ACTIVE: Duplicate tool calls, excessive consecutive file reads without edits, or exceeding ' + str(getattr(config, 'MAX_TURNS_PER_SESSION', 15)) + ' turns will immediately halt execution.\n') if getattr(config, 'GUARDRAILS_ENABLED', True) else '- SAFETY GUARDRAILS DISABLED: Unrestricted execution mode active per developer settings.\n'}"
                                f"- Follow AGENTS.md rules and keep documentation updated.\n"
                                f"- STANDARDIZED AGENT COMMENT RULE: When posting comments on GitHub issues/PRs, you MUST start with a standardized header badge (e.g., `🤖 **Agent Takeover: Development Started**` or `🤖 **Autonomous Agent**`) and include the disclaimer footer: `\\n\\n---\\n*Posted automatically by Agent Manager | Worktree: .worktrees/issue-{issue_num}*`.\n"
                                f"- CRITICAL RULE: Do NOT add, remove, or modify GitHub issue labels/tags. Status transitions are managed purely on the GitHub Project Board columns.\n"
                                f"- When done, commit changes, open a pull request, and summarize your work."
                            )
                            spawn_req = SpawnRequest(
                                repo=repo,
                                issue_number=issue_num,
                                title=title,
                                prompt=prompt
                            )
                            session = await self.runner.spawn_agent(spawn_req)
                            session.seen_comment_ids = [c.get("id") for c in comments if c.get("id")]
                            session.last_issue_body = body
                            self.runner._save()
