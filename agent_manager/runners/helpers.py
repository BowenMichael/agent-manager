import json
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

QUOTA_PATTERNS = (
    "quota", "resource_exhausted", "resource exhausted", "rate limit", "rate_limit",
    "429", "too many requests", "usage limit", "limit reached", "out of credits",
)


def looks_like_quota_error(text: str) -> bool:
    t = (text or "").lower()
    return any(p in t for p in QUOTA_PATTERNS)


def format_tool_display(tool_name: str, tool_args: Optional[dict] = None) -> tuple[str, str]:
    """Generates a human-friendly tool call title and descriptive summary from tool arguments."""
    name = tool_name or "tool"
    args = tool_args or {}

    if name == "view_file":
        target = args.get("AbsolutePath") or args.get("path") or ""
        base = target.replace("\\", "/").rstrip("/").split("/")[-1] if target else ""
        title = f"View File: {base}" if base else "View File"
        start_line = args.get("StartLine")
        end_line = args.get("EndLine")
        line_info = f" (lines {start_line}-{end_line})" if start_line is not None and end_line is not None else ""
        action = args.get("toolAction") or args.get("toolSummary")
        action_prefix = f"[{action}] " if action else ""
        desc = f"{action_prefix}{target}{line_info}".strip() or "Viewing file"
        return title, desc

    if name in ("replace_file_content", "write_to_file", "multi_replace_file_content"):
        target = args.get("TargetFile") or args.get("path") or ""
        base = target.replace("\\", "/").rstrip("/").split("/")[-1] if target else ""
        verb = "Write File" if name == "write_to_file" else "Edit File"
        title = f"{verb}: {base}" if base else verb
        instruction = args.get("Instruction") or args.get("Description") or args.get("toolAction") or args.get("toolSummary") or ""
        instr_str = f" - {instruction}" if instruction else ""
        desc = f"{target}{instr_str}".strip() or f"{verb} operation"
        return title, desc

    if name == "run_command":
        cmd = args.get("CommandLine") or args.get("command") or ""
        summary = args.get("toolSummary") or args.get("toolAction")
        title = f"Run: {summary}" if summary else "Run Command"
        desc = cmd or "Running shell command"
        return title, desc

    if name == "call_mcp_tool":
        sub_tool = args.get("ToolName") or "mcp_tool"
        server = args.get("ServerName")
        server_str = f"[{server}] " if server else ""
        title = f"MCP: {server_str}{sub_tool}"
        sub_args = args.get("Arguments")
        sub_args_str = json.dumps(sub_args) if isinstance(sub_args, dict) else (str(sub_args) if sub_args else "")
        desc = f"{sub_tool}({sub_args_str})" if sub_args_str else sub_tool
        return title, desc

    # Generic tool fallback
    summary = args.get("toolSummary") or args.get("toolAction")
    title = f"{name}: {summary}" if summary else f"Tool Call: {name}"
    params_summary = []
    for k, v in list(args.items())[:3]:
        if k in ("toolAction", "toolSummary"):
            continue
        v_str = str(v)
        if len(v_str) > 60:
            v_str = v_str[:57] + "..."
        params_summary.append(f"{k}={v_str}")
    desc = ", ".join(params_summary) if params_summary else f"Executing {name}"
    return title, desc


def _get_config_context(root: Path) -> List[str]:
    """Reads key manifest and configuration files from the target repository."""
    lines = []
    configs = [
        "package.json", "vercel.json", "next.config.js", "next.config.mjs",
        "tsconfig.json", "requirements.txt", "pyproject.toml", "Dockerfile", "render.yaml"
    ]
    for cfg in configs:
        cfg_path = root / cfg
        if cfg_path.exists() and cfg_path.is_file():
            try:
                content = cfg_path.read_text(encoding="utf-8", errors="replace").strip()
                if len(content) > 1500:
                    content = content[:1500] + "\n... (truncated)"
                lines.append(f"**Configuration File (`{cfg}`)**:\n```\n{content}\n```")
            except Exception:
                pass
    return lines


def _get_git_log_context(root: Path) -> List[str]:
    """Extracts recent git commit history for recent activity context."""
    try:
        res = subprocess.run(
            ["git", "log", "-n", "3", "--oneline"],
            cwd=str(root), capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0 and res.stdout.strip():
            return [f"**Recent Git History**:\n```\n{res.stdout.strip()}\n```"]
    except Exception:
        pass
    return []


def get_semantic_memory_context(query: str, top_k: int = 3) -> str:
    """Retrieves relevant cross-repository architectural context from shared vector memory."""
    if not query:
        return ""
    try:
        from agent_manager.services.memory_service import get_memory_service
        svc = get_memory_service()
        return svc.format_context(query, top_k=top_k)
    except Exception:
        return ""


def get_repository_context(cwd_dir: str, query: str = "") -> str:
    """Gathers repository structure, configs, git history, and semantic cross-repo memory."""
    context_lines = []
    root = Path(cwd_dir)
    if not root.exists():
        return "Repository directory not found."

    excluded = {".git", ".worktrees", "node_modules", ".next", "dist", "build", "__pycache__", ".venv", "venv", ".idea", ".vscode"}
    try:
        entries = sorted([p.name + ("/" if p.is_dir() else "") for p in root.iterdir() if p.name not in excluded and not p.name.startswith(".")])
        if entries:
            context_lines.append(f"**Directory Structure (Top Level)**:\n`{'`, `'.join(entries)}`")
    except Exception as e:
        context_lines.append(f"Directory listing error: {e}")

    context_lines.extend(_get_config_context(root))
    context_lines.extend(_get_git_log_context(root))

    mem_query = query or root.name
    mem_ctx = get_semantic_memory_context(mem_query, top_k=3)
    if mem_ctx:
        context_lines.append(mem_ctx)

    return "\n\n".join(context_lines) if context_lines else "No additional repository context discovered."

