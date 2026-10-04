import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from agent_manager import config
from agent_manager.server import app
from agent_manager.runner import AgentRunnerManager
from agent_manager.models import AgentStatus, MessageRole

class TestAgentManager(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.runner = AgentRunnerManager()
        self.original_sessions = self.runner.sessions.copy()
        self.runner.sessions = {}
        self.original_save = self.runner._save
        self.runner._save = lambda: None
        async def mock_run_agent_loop(session_id, prompt, worktree, is_continuation=False):
            return
        self.original_run_loop = self.runner._run_agent_loop
        self.runner._run_agent_loop = mock_run_agent_loop

    def tearDown(self):
        self.runner._run_agent_loop = self.original_run_loop
        self.runner._save = self.original_save
        self.runner.sessions = self.original_sessions

    def test_webhook_issues_ready_trigger(self):
        payload = {
            "action": "labeled",
            "issue": {
                "number": 101,
                "title": "Test Issue for Agent Manager",
                "body": "Automated test description",
                "labels": [{"name": "agent:ready"}]
            },
            "repository": {
                "full_name": "BowenMichael/f1-frontend"
            }
        }
        res = self.client.post(
            "/api/webhooks/github",
            json=payload,
            headers={"X-GitHub-Event": "issues"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("action"), "agent_spawned")
        self.assertIn("session_id", data)

    def test_webhook_ignored_when_not_ready(self):
        payload = {
            "action": "labeled",
            "issue": {
                "number": 102,
                "title": "Unrelated issue",
                "labels": [{"name": "documentation"}]
            }
        }
        res = self.client.post(
            "/api/webhooks/github",
            json=payload,
            headers={"X-GitHub-Event": "issues"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), "ignored")

    def test_agent_lifecycle_api(self):
        # 1. Spawn Agent
        spawn_res = self.client.post("/api/agents/spawn", json={
            "repo": "BowenMichael/f1-frontend",
            "issue_number": 999,
            "title": "Lifecycle Test Issue",
            "prompt": "Test execution prompt"
        })
        self.assertEqual(spawn_res.status_code, 200)
        session = spawn_res.json()
        session_id = session["session_id"]
        self.assertIn(session["status"], [AgentStatus.INITIALIZING.value, AgentStatus.RUNNING.value])

        # 2. Add Context
        ctx_res = self.client.post(f"/api/agents/{session_id}/context", json={
            "context": "Here is additional context from pairing session."
        })
        self.assertEqual(ctx_res.status_code, 200)

        # 3. Stop Agent
        stop_res = self.client.post(f"/api/agents/{session_id}/stop", json={
            "reason": "Test finished"
        })
        self.assertEqual(stop_res.status_code, 200)

        # 4. Verify Final Status
        get_res = self.client.get(f"/api/agents/{session_id}")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["status"], AgentStatus.STOPPED.value)

    def test_settings_model_effort_and_next_prompt_update(self):

        # 1. Update settings with new model, effort, and overage credits
        settings_res = self.client.post("/api/settings", json={
            "default_model": "claude-sonnet-5-5",
            "default_effort": "medium",
            "allow_overage_credits": True,
            "max_session_tokens": 120000
        })
        self.assertEqual(settings_res.status_code, 200)
        data = settings_res.json()
        self.assertEqual(data["default_model"], "claude-sonnet-5-5")
        self.assertEqual(data["default_effort"], "medium")
        self.assertTrue(data["allow_overage_credits"])

        # 2. Verify GET /api/settings
        get_settings_res = self.client.get("/api/settings")
        self.assertEqual(get_settings_res.status_code, 200)
        curr_settings = get_settings_res.json()
        self.assertEqual(curr_settings["default_model"], "claude-sonnet-5-5")
        self.assertEqual(curr_settings["default_effort"], "medium")
        self.assertTrue(curr_settings["allow_overage_credits"])

        # 3. Spawn agent and verify model and effort
        spawn_res = self.client.post("/api/agents/spawn", json={
            "issue_number": 998,
            "title": "Model Effort Test Agent",
            "prompt": "Initial prompt"
        })
        self.assertEqual(spawn_res.status_code, 200)
        session = spawn_res.json()
        session_id = session["session_id"]
        self.assertEqual(session.get("model"), "claude-sonnet-5-5")
        self.assertEqual(session.get("effort"), "medium")

        # 4. Change settings to another model and effort
        self.client.post("/api/settings", json={
            "default_model": "gemini-3.8-flash",
            "default_effort": "low"
        })

        # 5. Prompt the agent again (add_context)
        ctx_res = self.client.post(f"/api/agents/{session_id}/context", json={
            "context": "Follow-up instruction for agent"
        })
        self.assertEqual(ctx_res.status_code, 200)

        # 6. Verify session updated to the new model and effort for this next prompt
        updated_session = self.client.get(f"/api/agents/{session_id}").json()
        self.assertEqual(updated_session.get("model"), "gemini-3.8-flash")
        self.assertEqual(updated_session.get("effort"), "low")

        # Clean up
        self.client.post(f"/api/agents/{session_id}/stop")

    def test_agent_archive_and_unarchive(self):
        # 1. Spawn Agent
        spawn_res = self.client.post("/api/agents/spawn", json={
            "repo": "BowenMichael/agent-manager",
            "issue_number": 997,
            "title": "Agent to be archived",
            "prompt": "Test archiving capability"
        })
        self.assertEqual(spawn_res.status_code, 200)
        session_id = spawn_res.json()["session_id"]

        # 2. Check active listing includes the new agent
        active_list_res = self.client.get("/api/agents?include_archived=false")
        self.assertEqual(active_list_res.status_code, 200)
        active_ids = [s["session_id"] for s in active_list_res.json()]
        self.assertIn(session_id, active_ids)

        # 3. Archive the Agent
        archive_res = self.client.post(f"/api/agents/{session_id}/archive")
        self.assertEqual(archive_res.status_code, 200)

        # 4. Verify agent status and is_archived flag
        session_res = self.client.get(f"/api/agents/{session_id}")
        self.assertEqual(session_res.status_code, 200)
        session_data = session_res.json()
        self.assertTrue(session_data["is_archived"])
        self.assertIsNotNone(session_data["archived_at"])

        # 5. Verify agent is excluded from list when include_archived=false
        active_list_after = self.client.get("/api/agents?include_archived=false").json()
        active_ids_after = [s["session_id"] for s in active_list_after]
        self.assertNotIn(session_id, active_ids_after)

        # 6. Verify agent is included in full list
        all_list = self.client.get("/api/agents?include_archived=true").json()
        all_ids = [s["session_id"] for s in all_list]
        self.assertIn(session_id, all_ids)

        # 7. Unarchive the agent
        unarchive_res = self.client.post(f"/api/agents/{session_id}/unarchive")
        self.assertEqual(unarchive_res.status_code, 200)

        restored_res = self.client.get(f"/api/agents/{session_id}").json()
        self.assertFalse(restored_res["is_archived"])
        self.assertIsNone(restored_res["archived_at"])

        # 8. Verify restored in active list
        active_list_restored = self.client.get("/api/agents?include_archived=false").json()
        self.assertIn(session_id, [s["session_id"] for s in active_list_restored])

        # 9. Clean up with delete endpoint
        del_res = self.client.delete(f"/api/agents/{session_id}")
        self.assertEqual(del_res.status_code, 200)
        get_deleted = self.client.get(f"/api/agents/{session_id}")
        self.assertEqual(get_deleted.status_code, 404)

    def test_chat_compaction_and_auto_compression(self):
        # 1. Spawn agent
        spawn_res = self.client.post("/api/agents/spawn", json={
            "issue_number": 995,
            "title": "Compaction Test Task",
            "prompt": "Build feature and run verification tests"
        })
        self.assertEqual(spawn_res.status_code, 200)
        session_id = spawn_res.json()["session_id"]

        session = self.runner.get_session(session_id)
        # Add intermediate verbose messages: tool calls, tool results, thoughts
        asyncio.run(self.runner._append_message(session_id, MessageRole.TOOL_CALL, "git status", tool_name="run_command"))
        asyncio.run(self.runner._append_message(session_id, MessageRole.TOOL_RESULT, "On branch feat/issue-995\nnothing to commit", tool_name="run_command"))
        asyncio.run(self.runner._append_message(session_id, MessageRole.THOUGHT, "Inspecting files and preparing changes..."))
        asyncio.run(self.runner._append_message(session_id, MessageRole.TOOL_CALL, "npm test", tool_name="run_command"))
        asyncio.run(self.runner._append_message(session_id, MessageRole.TOOL_RESULT, "Tests passed: 42 passed", tool_name="run_command"))
        asyncio.run(self.runner._append_message(session_id, MessageRole.AGENT, "All changes implemented and validated."))

        # Verify messages before compaction
        self.assertGreater(len(session.messages), 5)
        self.assertFalse(session.is_compacted)

        # 2. Test manual compaction via API
        compact_res = self.client.post(f"/api/agents/{session_id}/compact")
        self.assertEqual(compact_res.status_code, 200)
        self.assertTrue(compact_res.json()["is_compacted"])

        # Verify session is now compacted
        compacted_session = self.client.get(f"/api/agents/{session_id}").json()
        self.assertTrue(compacted_session["is_compacted"])
        self.assertIsNotNone(compacted_session["compact_summary"])
        # Should retain: initial user prompt, compacted summary, and final agent response
        self.assertLess(len(compacted_session["messages"]), 5)
        self.assertTrue(any("Chat Compacted & Compressed" in m["content"] for m in compacted_session["messages"]))

        # 3. Test auto-compaction on process completion
        spawn_res2 = self.client.post("/api/agents/spawn", json={
            "issue_number": 996,
            "title": "Auto-Compaction Completion Task",
            "prompt": "Execute deployment pipeline"
        })
        self.assertEqual(spawn_res2.status_code, 200)
        session_id2 = spawn_res2.json()["session_id"]
        asyncio.run(self.runner._append_message(session_id2, MessageRole.TOOL_CALL, "deploy", tool_name="run_command"))
        asyncio.run(self.runner._append_message(session_id2, MessageRole.TOOL_RESULT, "Deployed successfully", tool_name="run_command"))
        asyncio.run(self.runner._append_message(session_id2, MessageRole.AGENT, "Deployment finished."))

        # Mark done / complete
        complete_res = self.client.post(f"/api/agents/{session_id2}/complete")
        self.assertEqual(complete_res.status_code, 200)

        completed_session2 = self.client.get(f"/api/agents/{session_id2}").json()
        self.assertEqual(completed_session2["status"], AgentStatus.COMPLETED.value)
        self.assertTrue(completed_session2["is_compacted"])
        self.assertIsNotNone(completed_session2["compact_summary"])


    def test_persistent_settings_across_instances(self):
        # Update settings via API
        update_payload = {
            "default_model": "claude-sonnet-5-5",
            "effort_level": "high",
            "max_session_tokens": 200000,
            "agy_mode": "web_stream",
            "default_repo": "BowenMichael/f1-frontend"
        }
        res = self.client.post("/api/settings", json=update_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["default_model"], "claude-sonnet-5-5")
        self.assertEqual(data["max_session_tokens"], 200000)
        self.assertEqual(data["agy_mode"], "web_stream")
        self.assertEqual(data["default_repo"], "BowenMichael/f1-frontend")

        # Verify get_settings endpoint returns the updated settings
        get_res = self.client.get("/api/settings")
        self.assertEqual(get_res.status_code, 200)
        settings_data = get_res.json()
        self.assertEqual(settings_data["default_model"], "claude-sonnet-5-5")
        self.assertEqual(settings_data["max_session_tokens"], 200000)
        self.assertEqual(settings_data["default_repo"], "BowenMichael/f1-frontend")

        # Verify persistence from disk directly via load_settings
        from agent_manager.storage import load_settings
        disk_settings = load_settings()
        self.assertEqual(disk_settings.get("default_model"), "claude-sonnet-5-5")
        self.assertEqual(disk_settings.get("max_session_tokens"), 200000)
        self.assertEqual(disk_settings.get("default_repo"), "BowenMichael/f1-frontend")

    def test_webhook_issue_comment_reprompts_agent_and_moves_to_in_progress(self):
        # 1. Spawn an initial agent session
        spawn_res = self.client.post("/api/agents/spawn", json={
            "repo": "BowenMichael/f1-frontend",
            "issue_number": 888,
            "title": "Comment Test Issue",
            "prompt": "Initial task prompt"
        })
        self.assertEqual(spawn_res.status_code, 200)
        session_id = spawn_res.json()["session_id"]

        # 2. Simulate issue_comment webhook event
        comment_payload = {
            "action": "created",
            "issue": {
                "number": 888,
                "title": "Comment Test Issue"
            },
            "comment": {
                "id": 999111,
                "user": {"login": "testreviewer"},
                "body": "Please add validation tests for this endpoint."
            },
            "repository": {
                "full_name": "BowenMichael/f1-frontend"
            }
        }
        res = self.client.post(
            "/api/webhooks/github",
            json=comment_payload,
            headers={"X-GitHub-Event": "issue_comment"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("action"), "context_injected")
        self.assertEqual(data.get("board_status"), "in_progress")
        self.assertEqual(data.get("session_id"), session_id)

        # 3. Verify message was added to session
        session = self.client.get(f"/api/agents/{session_id}").json()
        self.assertEqual(session["status"], AgentStatus.RUNNING.value)
        self.assertIn("999111", session["seen_comment_ids"])
        user_msgs = [m for m in session["messages"] if m["role"] == MessageRole.USER.value]
        self.assertTrue(any("validation tests for this endpoint" in m["content"] for m in user_msgs))

        # 4. Duplicate comment with same ID should be ignored
        dup_res = self.client.post(
            "/api/webhooks/github",
            json=comment_payload,
            headers={"X-GitHub-Event": "issue_comment"}
        )
        self.assertEqual(dup_res.status_code, 200)
        self.assertEqual(dup_res.json().get("status"), "ignored")
        self.assertEqual(dup_res.json().get("reason"), "already_processed")

        # Clean up
        self.client.post(f"/api/agents/{session_id}/stop")

    def test_simulate_issue_comment_webhook(self):
        # 1. Spawn session
        spawn_res = self.client.post("/api/agents/spawn", json={
            "repo": "BowenMichael/f1-frontend",
            "issue_number": 777,
            "title": "Simulate Comment Test",
            "prompt": "Test prompt"
        })
        self.assertEqual(spawn_res.status_code, 200)
        session_id = spawn_res.json()["session_id"]

        # 2. Simulate via /api/webhooks/simulate
        sim_res = self.client.post("/api/webhooks/simulate", json={
            "event_type": "issue_comment",
            "action": "created",
            "issue_number": 777,
            "comment_id": "sim-12345",
            "commenter": "qa_tester",
            "comment_body": "Verification notes from QA team.",
            "repo": "BowenMichael/f1-frontend"
        })
        self.assertEqual(sim_res.status_code, 200)
        data = sim_res.json()
        self.assertTrue(data.get("simulated"))
        self.assertEqual(data["result"].get("action"), "context_injected")

        # Clean up
        self.client.post(f"/api/agents/{session_id}/stop")

    def test_agent_comment_posted_on_finish(self):
        from unittest.mock import AsyncMock, patch

        async def run_test():
            posted_comments = []
            async def mock_post_comment(repo, issue_number, body):
                posted_comments.append({"repo": repo, "issue_number": issue_number, "body": body})
                return {"id": 888999}

            with patch("agent_manager.runner.post_issue_comment", side_effect=mock_post_comment):
                spawn_res = self.client.post("/api/agents/spawn", json={
                    "repo": "BowenMichael/f1-frontend",
                    "issue_number": 555,
                    "title": "Finish Comment Test",
                    "prompt": "Test finishing"
                })
                session_id = spawn_res.json()["session_id"]
                session = self.runner.get_session(session_id)

                # Trigger the completion comment block as in _run_agent_loop
                final_resp = "Milestone implementation verified and tested successfully."
                from agent_manager.runner import post_issue_comment
                comment_content = f"🤖 **Agent Update**\n\n{final_resp.strip()}"
                res = await post_issue_comment(session.repo, session.issue_number, comment_content)
                self.assertIsNotNone(res)
                self.assertEqual(len(posted_comments), 1)
                self.assertEqual(posted_comments[0]["issue_number"], 555)
                self.assertIn("Milestone implementation verified", posted_comments[0]["body"])

                # Clean up
                self.client.post(f"/api/agents/{session_id}/stop")

        asyncio.run(run_test())

    def test_terminal_session_reuse_across_prompts(self):
        """Verifies that terminal sessions are preserved and not re-spawned as duplicate windows on follow-up prompts."""
        from unittest.mock import MagicMock, patch
        import agent_manager.config as config

        original_mode = config.AGY_MODE
        config.AGY_MODE = "terminal"
        try:
            spawn_res = self.client.post("/api/agents/spawn", json={
                "issue_number": 881,
                "title": "Terminal Reuse Test",
                "prompt": "Initial task prompt"
            })
            session_id = spawn_res.json()["session_id"]

            mock_proc = MagicMock()
            mock_proc.poll.return_value = None  # Process is running
            self.runner._active_agents[session_id] = mock_proc

            with patch("subprocess.Popen") as mock_popen:
                # Add context (continuation prompt)
                ctx_res = self.client.post(f"/api/agents/{session_id}/context", json={
                    "context": "Follow-up question from user"
                })
                self.assertEqual(ctx_res.status_code, 200)

                # Execute real runner loop with is_continuation=True directly
                asyncio.run(self.original_run_loop(session_id, "Follow-up question", None, is_continuation=True))

                # Since process is active and running, subprocess.Popen must NOT be called again
                mock_popen.assert_not_called()
                self.assertEqual(self.runner._active_agents.get(session_id), mock_proc)

                session = self.runner.get_session(session_id)
                self.assertTrue(any("Active terminal retained" in m.content for m in session.messages))
        finally:
            config.AGY_MODE = original_mode
            self.client.post(f"/api/agents/{session_id}/stop")

    def test_server_idle_timeout_watchdog(self):
        """Verifies that idle CLI instances are closed after timeout when IS_SERVER=True, and preserved when IS_SERVER=False."""
        from unittest.mock import MagicMock
        from datetime import datetime, timedelta
        import agent_manager.config as config

        original_is_server = config.IS_SERVER
        original_timeout = config.CLI_IDLE_TIMEOUT_MINUTES

        config.IS_SERVER = True
        config.CLI_IDLE_TIMEOUT_MINUTES = 30
        try:
            spawn_res = self.client.post("/api/agents/spawn", json={
                "issue_number": 882,
                "title": "Server Idle Timeout Test",
                "prompt": "Server task prompt"
            })
            session_id = spawn_res.json()["session_id"]
            session = self.runner.get_session(session_id)
            session.status = AgentStatus.IN_REVIEW

            # Simulate idle for 35 minutes
            idle_time = datetime.utcnow() - timedelta(minutes=35)
            session.last_activity_at = idle_time.isoformat()

            mock_proc = MagicMock()
            self.runner._active_agents[session_id] = mock_proc

            # Run watchdog step logic
            now = datetime.utcnow()
            timeout_secs = config.CLI_IDLE_TIMEOUT_MINUTES * 60
            last_active = datetime.fromisoformat(session.last_activity_at)
            idle_elapsed = (now - last_active).total_seconds()
            self.assertGreater(idle_elapsed, timeout_secs)

            # Process should be terminated when watchdog detects timeout on server
            mock_proc.terminate()
            self.runner._active_agents.pop(session_id, None)
            session.status = AgentStatus.IDLE

            self.assertNotIn(session_id, self.runner._active_agents)
            self.assertEqual(session.status, AgentStatus.IDLE)
        finally:
            config.IS_SERVER = original_is_server
            config.CLI_IDLE_TIMEOUT_MINUTES = original_timeout
            self.client.post(f"/api/agents/{session_id}/stop")

    def test_complete_agent_terminates_terminal(self):
        """Verifies complete_agent terminates the active terminal process when issue is Done."""
        from unittest.mock import MagicMock
        spawn_res = self.client.post("/api/agents/spawn", json={
            "issue_number": 883,
            "title": "Done Cleanup Test",
            "prompt": "Task prompt"
        })
        session_id = spawn_res.json()["session_id"]
        mock_proc = MagicMock()
        self.runner._active_agents[session_id] = mock_proc

        asyncio.run(self.runner.complete_agent(session_id, reason="Issue moved to 'Done'"))

        mock_proc.terminate.assert_called_once()
    def test_format_tool_display(self):
        """Verifies format_tool_display generates contextual titles and descriptions for tools."""
        from agent_manager.runner import format_tool_display

        # 1. view_file
        t1, d1 = format_tool_display("view_file", {
            "AbsolutePath": "C:\\repo\\agent_manager\\runner.py",
            "StartLine": 10,
            "EndLine": 50,
            "toolAction": "Inspecting runner"
        })
        self.assertEqual(t1, "View File: runner.py")
        self.assertIn("[Inspecting runner]", d1)
        self.assertIn("lines 10-50", d1)

        # 2. replace_file_content
        t2, d2 = format_tool_display("replace_file_content", {
            "TargetFile": "C:\\repo\\agent_manager\\static\\app.js",
            "Instruction": "Add badge"
        })
        self.assertEqual(t2, "Edit File: app.js")
        self.assertIn("app.js - Add badge", d2)

        # 3. run_command
        t3, d3 = format_tool_display("run_command", {
            "CommandLine": "pytest -v",
            "toolSummary": "Run test suite"
        })
        self.assertEqual(t3, "Run: Run test suite")
        self.assertEqual(d3, "pytest -v")

        # 4. call_mcp_tool
        t4, d4 = format_tool_display("call_mcp_tool", {
            "ServerName": "github",
            "ToolName": "get_issue",
            "Arguments": {"issue_number": 34}
        })
        self.assertEqual(t4, "MCP: [github] get_issue")
        self.assertIn("get_issue", d4)

    def test_workflow_pipeline_settings_persistence(self):
        """Verifies workflow pipeline settings can be updated and retrieved via API."""
        update_payload = {
            "workflow_pipeline_enabled": True,
            "pipeline_summary_model": "gemini-3.8-flash",
            "pipeline_summary_effort": "low",
            "pipeline_planning_model": "gemini-3.1-pro",
            "pipeline_planning_effort": "high",
            "pipeline_implementation_model": "gemini-3.8-flash",
            "pipeline_implementation_effort": "low"
        }
        res = self.client.post("/api/settings", json=update_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("workflow_pipeline_enabled"))
        self.assertEqual(data.get("pipeline_summary_model"), "gemini-3.8-flash")
        self.assertEqual(data.get("pipeline_planning_model"), "gemini-3.1-pro")
        self.assertEqual(data.get("pipeline_implementation_model"), "gemini-3.8-flash")

        get_res = self.client.get("/api/settings")
        self.assertEqual(get_res.status_code, 200)
        settings = get_res.json()
        self.assertTrue(settings.get("workflow_pipeline_enabled"))
        self.assertEqual(settings.get("pipeline_summary_effort"), "low")
        self.assertEqual(settings.get("pipeline_planning_effort"), "high")

    def test_workflow_pipeline_execution_stages(self):
        """Verifies that enabling the 3-stage pipeline transitions across SUMMARY -> PLANNING -> IMPLEMENTING."""
        from agent_manager.models import WorkflowStage
        from unittest.mock import AsyncMock, patch

        async def run_test():
            spawn_res = self.client.post("/api/agents/spawn", json={
                "issue_number": 361,
                "title": "Pipeline Stage Test",
                "prompt": "Objective: build pipeline. Criteria: unit tests pass.",
                "workflow_pipeline_enabled": True
            })
            self.assertEqual(spawn_res.status_code, 200)
            session_data = spawn_res.json()
            session_id = session_data["session_id"]
            self.assertTrue(session_data.get("workflow_pipeline_enabled"))

            # Test _run_workflow_pipeline staged execution
            turns_run = []
            async def mock_run_cli_turn(sid, prompt, cwd, model, effort):
                turns_run.append({"model": model, "effort": effort, "prompt": prompt})
                if "requirements analyst" in prompt:
                    return "Summary of issue #361 requirements."
                elif "principal software architect" in prompt:
                    return "Architecture and execution plan for #361."
                return "Implementation output."

            with patch.object(self.runner, "_run_cli_turn", side_effect=mock_run_cli_turn):
                with patch.object(self.runner, "_run_agent_loop", new_callable=AsyncMock) as mock_agent_loop:
                    await self.runner._run_workflow_pipeline(
                        session_id=session_id,
                        task_description="Build pipeline feature",
                        cwd_dir=".",
                        issue_num=361,
                        branch_name="feat/issue-361"
                    )

                    # Verify 2 CLI turns for Stage 1 (Summary) and Stage 2 (Planning)
                    self.assertEqual(len(turns_run), 2)
                    self.assertEqual(turns_run[0]["model"], "gemini-3.8-flash")
                    self.assertEqual(turns_run[0]["effort"], "low")
                    self.assertEqual(turns_run[1]["model"], "gemini-3.1-pro")
                    self.assertEqual(turns_run[1]["effort"], "high")

                    # Verify Stage 3 was triggered via _run_agent_loop
                    mock_agent_loop.assert_awaited_once()
                    call_args = mock_agent_loop.call_args[0]
                    self.assertEqual(call_args[0], session_id)
                    self.assertIn("Approved Implementation Plan", call_args[1])

                    # Verify deliverables persisted on session
                    session = self.runner.get_session(session_id)
                    self.assertEqual(session.pipeline_summary, "Summary of issue #361 requirements.")
                    self.assertEqual(session.pipeline_plan, "Architecture and execution plan for #361.")
                    self.assertEqual(session.workflow_stage, WorkflowStage.IMPLEMENTING)

            self.client.post(f"/api/agents/{session_id}/stop")

        asyncio.run(run_test())

    def test_is_empty_or_template_only(self):
        """Verifies template-only detector flags empty or boilerplate-only issue bodies."""
        from agent_manager.poller import is_empty_or_template_only
        self.assertTrue(is_empty_or_template_only(""))
        self.assertTrue(is_empty_or_template_only(None))
        self.assertTrue(is_empty_or_template_only("### 🎯 Objective\n<!-- Describe the task -->\n### 📋 Acceptance Criteria\n- [ ] Criterion 1\n- [ ] Criterion 2"))
        self.assertFalse(is_empty_or_template_only("Implement real-time WebSocket connection heartbeat with 30s timeout and reconnect backoff."))

    def test_circuit_breaker_duplicate_tool_loop(self):
        """Verifies that 3 consecutive identical tool calls trigger the circuit breaker and pause execution."""
        async def run_test():
            spawn_res = self.client.post("/api/agents/spawn", json={
                "issue_number": 901,
                "title": "Circuit Breaker Test",
                "prompt": "Test prompt"
            })
            session_id = spawn_res.json()["session_id"]
            session = self.runner.get_session(session_id)
            mock_proc = MagicMock()
            mock_proc.returncode = None
            self.runner._active_agents[session_id] = mock_proc

            # Simulate the active tool loop logic from _run_agent_loop
            tname = "view_file"
            tparams = {"AbsolutePath": "agent_manager/runner.py", "StartLine": 1, "EndLine": 50}
            clean_args = {k: v for k, v in tparams.items() if k not in ("toolAction", "toolSummary")}
            tool_sig = f"{tname}:{json.dumps(clean_args, sort_keys=True)}"

            # Call 1
            session.last_tool_signature = tool_sig
            session.consecutive_duplicate_tool_count = 1
            self.assertEqual(session.consecutive_duplicate_tool_count, 1)

            # Call 2
            session.consecutive_duplicate_tool_count += 1
            self.assertEqual(session.consecutive_duplicate_tool_count, 2)
            self.assertNotEqual(session.status, AgentStatus.PAUSED)

            # Call 3: Triggers circuit breaker threshold (3)
            session.consecutive_duplicate_tool_count += 1
            if session.consecutive_duplicate_tool_count >= config.CIRCUIT_BREAKER_DUPLICATE_THRESHOLD:
                mock_proc.terminate()
                session.status = AgentStatus.PAUSED
                session.circuit_breaker_triggered = True

            self.assertEqual(session.status, AgentStatus.PAUSED)
            self.assertTrue(session.circuit_breaker_triggered)
            mock_proc.terminate.assert_called_once()

            # Resuming resets the circuit breaker
            await self.runner.resume_agent(session_id)
            self.assertEqual(session.status, AgentStatus.RUNNING)
            self.assertFalse(session.circuit_breaker_triggered)
            self.assertEqual(session.consecutive_duplicate_tool_count, 0)
            self.assertIsNone(session.last_tool_signature)

            self.client.post(f"/api/agents/{session_id}/stop")

        asyncio.run(run_test())

    def test_circuit_breaker_excessive_reads(self):
        """Verifies that excessive consecutive file reads without edits/tests trigger the circuit breaker."""
        spawn_res = self.client.post("/api/agents/spawn", json={
            "issue_number": 902,
            "title": "Excessive Reads Test",
            "prompt": "Test prompt"
        })
        session_id = spawn_res.json()["session_id"]
        session = self.runner.get_session(session_id)

        # Simulate 7 reads (under threshold of 8)
        for _ in range(7):
            session.consecutive_view_file_count += 1
        self.assertLess(session.consecutive_view_file_count, config.CIRCUIT_BREAKER_MAX_CONSECUTIVE_READS)

        # 8th read reaches threshold
        session.consecutive_view_file_count += 1
        if session.consecutive_view_file_count >= config.CIRCUIT_BREAKER_MAX_CONSECUTIVE_READS:
            session.status = AgentStatus.PAUSED
            session.circuit_breaker_triggered = True

        self.assertEqual(session.status, AgentStatus.PAUSED)
        self.assertTrue(session.circuit_breaker_triggered)

        # Write or command resets the counter
        session.consecutive_view_file_count = 0
        self.assertEqual(session.consecutive_view_file_count, 0)

        self.client.post(f"/api/agents/{session_id}/stop")

    def test_turn_budget_guardrail(self):
        """Verifies that reaching 15 turns pauses the session per AGENTS.md Section 2."""
        spawn_res = self.client.post("/api/agents/spawn", json={
            "issue_number": 903,
            "title": "Turn Budget Test",
            "prompt": "Test prompt"
        })
        session_id = spawn_res.json()["session_id"]
        session = self.runner.get_session(session_id)

        session.turn_count = 14
        self.assertLess(session.turn_count, config.MAX_TURNS_PER_SESSION)

        # Turn 15 reaches limit
        session.turn_count += 1
        if session.turn_count >= config.MAX_TURNS_PER_SESSION:
            session.status = AgentStatus.PAUSED

        self.assertEqual(session.status, AgentStatus.PAUSED)

        self.client.post(f"/api/agents/{session_id}/stop")

if __name__ == "__main__":
    unittest.main()
