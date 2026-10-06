"""
Unit & Integration Tests for Peer Reviewer Gateway & Security Audit Service.
Verifies secret scanning, AST vulnerability detection, function LOC enforcement,
PR review markdown synthesis, and gate blocking behavior.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import asyncio
import tempfile
import unittest
from pathlib import Path

from agent_manager.models import AgentSessionInfo, AgentStatus
from agent_manager.services.security_audit_service import (
    scan_content_for_secrets, audit_python_ast, audit_worktree_diff
)
from agent_manager.runners.reviewer import (
    format_review_markdown, run_peer_reviewer_gateway
)


class TestSecurityAuditService(unittest.TestCase):
    def test_scan_content_for_secrets_detects_credentials(self):
        clean_content = "def calculate_sum(a, b):\n    return a + b\n"
        self.assertEqual(scan_content_for_secrets(clean_content, "clean.py"), [])

        dirty_content = 'API_KEY = "AKIA1234567890ABCDEF"\nghp = "ghp_123456789012345678901234567890123456"\n'
        findings = scan_content_for_secrets(dirty_content, "leak.py")
        self.assertGreaterEqual(len(findings), 2)
        self.assertTrue(any("AWS Access Key" in f["description"] for f in findings))
        self.assertTrue(any("GitHub Personal Access Token" in f["description"] for f in findings))

    def test_audit_python_ast_detects_eval_and_shell_true(self):
        vulnerable_code = (
            "import subprocess\n"
            "def run_command(cmd):\n"
            "    eval(cmd)\n"
            "    subprocess.run(cmd, shell=True)\n"
        )
        res = audit_python_ast(vulnerable_code, "vuln.py")
        self.assertIsNone(res["syntax_error"])
        sec = res["security_issues"]
        self.assertGreaterEqual(len(sec), 2)
        descriptions = [s["description"] for s in sec]
        self.assertTrue(any("eval" in d for d in descriptions))
        self.assertTrue(any("shell=True" in d for d in descriptions))

    def test_audit_python_ast_detects_bloated_functions(self):
        lines = ["def huge_function():\n"]
        for i in range(45):
            lines.append(f"    x_{i} = {i}\n")
        lines.append("    return x_0\n")
        long_func_code = "".join(lines)

        res = audit_python_ast(long_func_code, "bloat.py")
        self.assertEqual(len(res["monolith_issues"]), 1)
        self.assertIn("exceeds 40 LOC limit", res["monolith_issues"][0]["description"])

    def test_audit_worktree_diff_with_clean_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            clean_file = tmp_path / "service.py"
            clean_file.write_text("def ping():\n    return 'pong'\n", encoding="utf-8")

            res = audit_worktree_diff(tmp_path)
            self.assertTrue(res["passed"])
            self.assertEqual(len(res["critical_flaws"]), 0)

    def test_audit_worktree_diff_with_critical_flaws(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            bad_file = tmp_path / "bad.py"
            bad_file.write_text('SECRET_TOKEN = "ghp_123456789012345678901234567890123456"\neval("2+2")\n', encoding="utf-8")

            # Mock get_git_diff_files to return bad.py
            import agent_manager.services.security_audit_service as sas
            orig = sas.get_git_diff_files
            sas.get_git_diff_files = lambda p, b="main": ["bad.py"]
            try:
                res = audit_worktree_diff(tmp_path)
                self.assertFalse(res["passed"])
                self.assertGreaterEqual(len(res["critical_flaws"]), 2)
            finally:
                sas.get_git_diff_files = orig


class TestReviewerRunner(unittest.TestCase):
    def test_format_review_markdown(self):
        clean_res = {"passed": True, "critical_flaws": [], "warnings": [], "changed_files": ["foo.py"]}
        md_approve = format_review_markdown(clean_res, "feat/clean")
        self.assertIn("APPROVE", md_approve)

        flawed_res = {
            "passed": False,
            "critical_flaws": ["eval() call detected"],
            "warnings": ["No test files found"],
            "changed_files": ["bar.py"]
        }
        md_reject = format_review_markdown(flawed_res, "feat/flawed")
        self.assertIn("REQUEST CHANGES", md_reject)
        self.assertIn("Critical Blockers", md_reject)

    def test_run_peer_reviewer_gateway_blocks_on_failure(self):
        session = AgentSessionInfo(
            session_id="test-review-sess",
            repo="BowenMichael/agent-manager",
            title="Peer Review Test",
            status=AgentStatus.RUNNING
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            bad_file = tmp_path / "leaky.py"
            bad_file.write_text('TOKEN = "ghp_123456789012345678901234567890123456"\n', encoding="utf-8")

            import agent_manager.services.security_audit_service as sas
            orig = sas.get_git_diff_files
            sas.get_git_diff_files = lambda p, b="main": ["leaky.py"]
            try:
                res = asyncio.run(run_peer_reviewer_gateway(session, tmp_path, "feat/leaky"))
                self.assertFalse(res["passed"])
                self.assertEqual(res["event"], "REQUEST_CHANGES")
                self.assertGreaterEqual(len(session.messages), 1)
                self.assertIn("REQUEST CHANGES", session.messages[-1].content)
            finally:
                sas.get_git_diff_files = orig


if __name__ == "__main__":
    unittest.main()
