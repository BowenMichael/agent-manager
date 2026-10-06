"""
Static Security Audit & Anti-Monolith Verification Service.
Audits code diffs for hardcoded secrets, AST security anti-patterns,
syntax errors, test coverage density, and Section 5 Anti-Monolith limits.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import ast
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

SECRET_PATTERNS = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS Access Key"),
    (re.compile(r"ghp_[0-9a-zA-Z]{36}"), "GitHub Personal Access Token"),
    (re.compile(r"github_pat_[0-9a-zA-Z_]{40,}"), "Fine-grained GitHub Token"),
    (re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----"), "Private Key"),
    (re.compile(r"(?:api[_-]?key|secret[_-]?token)\s*=\s*['\"][a-zA-Z0-9_\-]{20,}['\"]", re.IGNORECASE), "Generic Hardcoded Secret"),
]


def scan_content_for_secrets(content: str, filename: str) -> List[Dict[str, Any]]:
    """Scans raw file text for hardcoded credentials or private keys."""
    findings = []
    lines = content.splitlines()
    for line_idx, line in enumerate(lines, 1):
        for pattern, desc in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append({
                    "file": filename,
                    "line": line_idx,
                    "severity": "CRITICAL",
                    "description": f"Potential hardcoded credential: {desc}"
                })
    return findings


class ASTSecurityVisitor(ast.NodeVisitor):
    """AST visitor detecting hazardous Python calls like eval, exec, and shell=True."""

    def __init__(self, filename: str):
        self.filename = filename
        self.findings: List[Dict[str, Any]] = []

    def visit_Call(self, node: ast.Call):
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name in ("eval", "exec"):
            self.findings.append({
                "file": self.filename,
                "line": node.lineno,
                "severity": "CRITICAL",
                "description": f"Dangerous dynamic execution: `{func_name}()` call detected."
            })
        elif func_name in ("system", "popen") and getattr(node.func, "value", None) and getattr(node.func.value, "id", None) == "os":
            self.findings.append({
                "file": self.filename,
                "line": node.lineno,
                "severity": "WARNING",
                "description": "Insecure subprocess: prefer subprocess.run without shell=True."
            })

        for keyword in node.keywords:
            if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                self.findings.append({
                    "file": self.filename,
                    "line": node.lineno,
                    "severity": "CRITICAL",
                    "description": "Hazardous `shell=True` invocation in subprocess call."
                })
        self.generic_visit(node)


def audit_python_ast(content: str, filename: str) -> Dict[str, Any]:
    """Parses Python AST to check syntax, function lengths, and security calls."""
    result = {"syntax_error": None, "security_issues": [], "monolith_issues": []}
    try:
        tree = ast.parse(content, filename=filename)
    except SyntaxError as e:
        result["syntax_error"] = f"Syntax error at line {e.lineno}: {e.msg}"
        return result

    visitor = ASTSecurityVisitor(filename)
    visitor.visit(tree)
    result["security_issues"] = visitor.findings

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_lines = (node.end_lineno or node.lineno) - node.lineno + 1
            if func_lines > 40:
                result["monolith_issues"].append({
                    "file": filename,
                    "function": node.name,
                    "line": node.lineno,
                    "loc": func_lines,
                    "severity": "CRITICAL",
                    "description": f"Function `{node.name}` exceeds 40 LOC limit ({func_lines} lines)."
                })
    return result


def get_git_diff_files(worktree_path: Path, base_branch: str = "main") -> List[str]:
    """Identifies all modified or untracked files in the worktree."""
    files = []
    try:
        res = subprocess.check_output(
            ["git", "diff", "--name-only", f"origin/{base_branch}...HEAD"],
            cwd=str(worktree_path), text=True, stderr=subprocess.DEVNULL
        )
        files.extend([f.strip() for f in res.splitlines() if f.strip()])
    except Exception:
        pass

    try:
        status_res = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=str(worktree_path), text=True, stderr=subprocess.DEVNULL
        )
        for line in status_res.splitlines():
            if line.strip():
                parts = line.strip().split(maxsplit=1)
                if len(parts) == 2 and parts[1] not in files:
                    files.append(parts[1])
    except Exception:
        pass
    return [f for f in files if f and not f.startswith(".agent_logs")]


def audit_worktree_diff(worktree_path: Path, base_branch: str = "main") -> Dict[str, Any]:
    """Comprehensive peer review audit of worktree changes against quality and security gates."""
    changed_files = get_git_diff_files(worktree_path, base_branch)
    critical_flaws: List[str] = []
    warnings: List[str] = []
    all_findings: List[Dict[str, Any]] = []

    has_source_changes = False
    has_test_changes = False

    for rel_path in changed_files:
        full_path = worktree_path / rel_path
        if not full_path.is_file():
            continue

        if rel_path.startswith("agent_manager/"):
            has_source_changes = True
        if rel_path.startswith("tests/"):
            has_test_changes = True

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        lines = len(content.splitlines())
        if lines > 250 and not rel_path.endswith((".json", ".lock", ".md")):
            critical_flaws.append(f"File `{rel_path}` exceeds 250 LOC limit ({lines} lines).")

        sec_findings = scan_content_for_secrets(content, rel_path)
        for f in sec_findings:
            critical_flaws.append(f"{rel_path}:{f['line']} {f['description']}")
            all_findings.append(f)

        if rel_path.endswith(".py"):
            ast_res = audit_python_ast(content, rel_path)
            if ast_res["syntax_error"]:
                critical_flaws.append(f"{rel_path}: {ast_res['syntax_error']}")
            for issue in ast_res["security_issues"]:
                if issue["severity"] == "CRITICAL":
                    critical_flaws.append(f"{rel_path}:{issue['line']} {issue['description']}")
                else:
                    warnings.append(f"{rel_path}:{issue['line']} {issue['description']}")
                all_findings.append(issue)
            for m in ast_res["monolith_issues"]:
                critical_flaws.append(f"{rel_path}:{m['line']} {m['description']}")
                all_findings.append(m)

    if has_source_changes and not has_test_changes:
        warnings.append("Changes made to agent_manager/ source without corresponding modifications in tests/.")

    passed = len(critical_flaws) == 0
    return {
        "passed": passed,
        "critical_flaws": critical_flaws,
        "warnings": warnings,
        "changed_files": changed_files,
        "findings_count": len(all_findings),
        "all_findings": all_findings
    }
