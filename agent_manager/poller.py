import asyncio
import logging
import httpx
from typing import Optional, Set, Dict

from agent_manager.config import (
    GITHUB_PERSONAL_ACCESS_TOKEN, PROJECT_BOARD_ID, PROJECT_BOARD_IDS,
    DEFAULT_REPO, POLL_INTERVAL_SECONDS
)
from agent_manager.models import SpawnRequest, AgentStatus
from agent_manager.runner import AgentRunnerManager

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

class LocalGitWatcher:
    """
    Local Git & Project Board Synchronizer.
    Enables 100% local agent dispatching without opening external ports or tunnels.
    Moves board status directly without adding tags/labels to issues.
    Ensures chats stay open until manually moved into 'Done'.
    Detects re-queued tasks and checks for new comments or modifications.
    """
    def __init__(self):
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

    async def update_item_status(self, item_id: str, status_key: str) -> bool:
        """Updates the status column directly on GitHub Project Board V2 without touching issue tags."""
        project_id = self.item_project_map.get(item_id, PROJECT_BOARD_ID)
        board = await self._resolve_board_fields(project_id)
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
                            "projectId": project_id,
                            "itemId": item_id,
                            "fieldId": board["field_id"],
                            "optionId": option_id
                        }
                    },
                    headers=headers
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error("Failed to update item status: %s", e)
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
                repo = content.get("repository", {}).get("nameWithOwner", DEFAULT_REPO)
                comments = content.get("comments", {}).get("nodes", [])
                issue_key = f"{repo}#{issue_num}"
                self.item_id_map[issue_key] = item["id"]
                self.item_project_map[item["id"]] = project_id

                # 1. LIFECYCLE: Completed only when manually moved to Done
                if status_name == STATUS_NAMES["done"]:
                    for s in self.runner.list_sessions():
                        if s.issue_number == issue_num and s.repo == repo and s.status != AgentStatus.COMPLETED:
                            logger.info("Issue #%s detected in '✅ Done'. Formally completing and archiving session %s", issue_num, s.session_id)
                            await self.runner.complete_agent(s.session_id, reason="Issue moved to 'Done' on GitHub Project Board")
                    self.active_issues.discard(issue_key)
                    continue

                # 2. AUTO-SYNC: If session is IN_REVIEW, ensure Project Board is marked In Review
                for s in self.runner.list_sessions():
                    if s.issue_number == issue_num and s.repo == repo and s.status == AgentStatus.IN_REVIEW:
                        if status_name == "⚡ In Progress":
                            await self.update_item_status(item["id"], "in_review")
                            logger.info("Updated Issue #%s Project Board status to '🔍 In Review'", issue_num)

                # 3. RE-QUEUE & NEW ISSUE: Status is '📋 Ready for Agent'
                if status_name == STATUS_NAMES["ready"]:
                    existing_session = next(
                        (s for s in self.runner.list_sessions() if s.issue_number == issue_num and s.repo == repo),
                        None
                    )

                    if existing_session:
                        # Check what has been added to the issue since last run
                        new_comments = [
                            c for c in comments
                            if c.get("id") not in existing_session.seen_comment_ids
                            and not (c.get("body") or "").startswith("🤖 **Agent")
                            and not (c.get("body") or "").startswith("🚀 **Task Complete")
                        ]
                        body_changed = (
                            existing_session.last_issue_body is not None and
                            body.strip() != existing_session.last_issue_body.strip()
                        )

                        if new_comments or body_changed:
                            update_sections = []
                            if body_changed:
                                update_sections.append(f"### Updated Issue Description:\n{body.strip()}")
                            if new_comments:
                                update_sections.append("### New Comments Added by User:")
                                for nc in new_comments:
                                    author = nc.get("author", {}).get("login", "User")
                                    update_sections.append(f"- **@{author}**: {nc.get('body', '').strip()}")

                            feedback_text = "\n\n".join(update_sections)
                            logger.info("Issue #%s was moved back to Ready for Agent with new updates (%d new comments). Injecting continuation context.", issue_num, len(new_comments))

                            # Update seen comments and body
                            for c in comments:
                                if c.get("id") not in existing_session.seen_comment_ids:
                                    existing_session.seen_comment_ids.append(c.get("id"))
                            existing_session.last_issue_body = body
                            self.runner._save()

                            # Move status on board to In Progress
                            await self.update_item_status(item["id"], "in_progress")
                            logger.info("Updated Issue #%s Project Board status to '⚡ In Progress'", issue_num)

                            continuation_prompt = (
                                f"Issue #{issue_num} was moved back to Ready for Agent with new updates:\n\n"
                                f"{feedback_text}\n\n"
                                f"**Operational Instructions**:\n"
                                f"- Work inside the existing isolated worktree ({existing_session.worktree_path}) and branch ({existing_session.git_branch}).\n"
                                f"- Address all new requirements and user feedback.\n"
                                f"- Follow AGENTS.md rules: do not add issue labels, keep status transitions purely on the Project Board.\n"
                                f"- Commit changes, push to branch, and report your progress."
                            )
                            await self.runner.add_context(existing_session.session_id, continuation_prompt)

                        elif existing_session.status in [AgentStatus.IN_REVIEW, AgentStatus.IDLE, AgentStatus.PAUSED]:
                            # No new text added, but user dragged it back to Ready for Agent
                            logger.info("Issue #%s moved back to Ready for Agent with no new comments. Triggering continuation pass.", issue_num)
                            for c in comments:
                                if c.get("id") not in existing_session.seen_comment_ids:
                                    existing_session.seen_comment_ids.append(c.get("id"))
                            existing_session.last_issue_body = body
                            self.runner._save()

                            await self.update_item_status(item["id"], "in_progress")
                            continuation_prompt = (
                                f"Issue #{issue_num} has been moved back into Ready for Agent.\n"
                                f"Please review the work completed in the worktree, test existing features, and continue working on any remaining requirements."
                            )
                            await self.runner.add_context(existing_session.session_id, continuation_prompt)

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

                            prompt = (
                                f"You have been assigned to GitHub Issue #{issue_num} in {repo}.\n\n"
                                f"**Title**: {title}\n\n"
                                f"**Requirements / Description**:\n{body}\n\n"
                                f"**Operational Guidelines**:\n"
                                f"- Work inside the designated branch and isolated worktree .worktrees/issue-{issue_num}.\n"
                                f"- Inspect existing code patterns before modifying.\n"
                                f"- Follow AGENTS.md rules and keep documentation updated.\n"
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
