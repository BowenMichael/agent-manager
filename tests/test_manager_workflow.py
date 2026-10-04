import asyncio
import unittest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from agent_manager.server import app
from agent_manager.runner import AgentRunnerManager
from agent_manager.models import WorkflowStage

class TestManagerWorkflow(unittest.TestCase):
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

                    self.assertEqual(len(turns_run), 2)
                    self.assertEqual(turns_run[0]["model"], "gemini-3.8-flash")
                    self.assertEqual(turns_run[0]["effort"], "low")
                    self.assertEqual(turns_run[1]["model"], "gemini-3.1-pro")
                    self.assertEqual(turns_run[1]["effort"], "high")

                    self.assertIn("Codebase Context", turns_run[1]["prompt"])

                    mock_agent_loop.assert_awaited_once()
                    call_args = mock_agent_loop.call_args[0]
                    self.assertEqual(call_args[0], session_id)
                    self.assertIn("Approved Implementation Plan", call_args[1])

                    session = self.runner.get_session(session_id)
                    self.assertEqual(session.pipeline_summary, "Summary of issue #361 requirements.")
                    self.assertEqual(session.pipeline_plan, "Architecture and execution plan for #361.")
                    self.assertEqual(session.workflow_stage, WorkflowStage.IMPLEMENTING)

            self.client.post(f"/api/agents/{session_id}/stop")

        asyncio.run(run_test())

    def test_get_repository_context(self):
        """Verifies get_repository_context extracts directory structure, configs, and git history."""
        from agent_manager.runner import get_repository_context
        ctx = get_repository_context(".")
        self.assertIn("Directory Structure", ctx)

    def test_is_empty_or_template_only(self):
        """Verifies template-only detector flags empty or boilerplate-only issue bodies."""
        from agent_manager.poller import is_empty_or_template_only
        self.assertTrue(is_empty_or_template_only(""))
        self.assertTrue(is_empty_or_template_only(None))
        self.assertTrue(is_empty_or_template_only("### 🎯 Objective\n<!-- Describe the task -->\n### 📋 Acceptance Criteria\n- [ ] Criterion 1\n- [ ] Criterion 2"))
        self.assertFalse(is_empty_or_template_only("Implement real-time WebSocket connection heartbeat with 30s timeout and reconnect backoff."))

    def test_format_tool_display(self):
        """Verifies format_tool_display generates contextual titles and descriptions for tools."""
        from agent_manager.runner import format_tool_display

        t1, d1 = format_tool_display("view_file", {
            "AbsolutePath": "C:\\repo\\agent_manager\\runner.py",
            "StartLine": 10,
            "EndLine": 50,
            "toolAction": "Inspecting runner"
        })
        self.assertEqual(t1, "View File: runner.py")
        self.assertIn("[Inspecting runner]", d1)
        self.assertIn("lines 10-50", d1)

if __name__ == "__main__":
    unittest.main()
