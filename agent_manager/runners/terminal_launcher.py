"""
Cross-Platform Terminal Launcher.
Spawns interactive terminal consoles for agents on Windows (PowerShell) and POSIX systems.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from agent_manager.models import MessageRole, AgentStatus
from agent_manager.config import AGY_CLI_PATH

SUBPROCESS_CREATE_NEW_CONSOLE = 0x00000010


def _build_windows_script(issue_num: int, clean_model: str, clean_effort: str, cli_model_args: list, target_prompt: str, is_continuation: bool) -> str:
    """Formats PowerShell launcher script with UTF-8 encoding and prompt string."""
    title_str = f"Antigravity CLI (agy) - Issue #{issue_num} [{clean_model} / {clean_effort}]"
    safe_prompt = target_prompt.replace('@"', '`@"').replace('"@', '`"@')
    continue_flag = "--continue" if is_continuation else ""
    return "\n".join([
        "$OutputEncoding = [System.Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()",
        f"$host.ui.RawUI.WindowTitle = '{title_str}'",
        f"Write-Host '🚀 Launching Antigravity CLI for Issue #{issue_num} [{clean_model}]...' -ForegroundColor Cyan",
        "$promptText = @\"",
        safe_prompt,
        "\"@",
        f"& \"{AGY_CLI_PATH}\" {' '.join(cli_model_args)} {continue_flag} --dangerously-skip-permissions -i $promptText"
    ])


async def _launch_windows(manager, session, issue_num: int, clean_model: str, clean_effort: str, cli_model_args: list, cwd_dir: str, target_prompt: str, is_continuation: bool) -> bool:
    """Spawns dedicated PowerShell interactive console on Windows."""
    script_content = _build_windows_script(issue_num, clean_model, clean_effort, cli_model_args, target_prompt, is_continuation)
    launcher_path = Path(cwd_dir) / ".agy_terminal_launch.ps1"
    launcher_path.write_text(script_content, encoding="utf-8")

    continue_flag = "--continue" if is_continuation else ""
    session.terminal_command = f'& "{AGY_CLI_PATH}" {" ".join(cli_model_args)} {continue_flag} --dangerously-skip-permissions'

    await manager._append_message(
        session.session_id,
        MessageRole.SYSTEM,
        f"🚀 [Interactive Terminal] Spawning Antigravity CLI in PowerShell at: {cwd_dir}\nModel: {clean_model} • Effort: {clean_effort}"
    )
    proc = subprocess.Popen(
        ["powershell.exe", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", str(launcher_path)],
        cwd=str(cwd_dir),
        creationflags=SUBPROCESS_CREATE_NEW_CONSOLE
    )
    manager._active_agents[session.session_id] = proc
    session.status = AgentStatus.IN_REVIEW
    manager._save()
    await manager.broadcast("session_updated", session.model_dump())
    return True


async def launch_desktop_terminal(manager, session, issue_num: int, clean_model: str, clean_effort: str, cli_model_args: list, cwd_dir: str, target_prompt: str, is_continuation: bool) -> bool:
    """Spawns an interactive desktop terminal session across Windows and Unix platforms."""
    if sys.platform == "win32":
        return await _launch_windows(manager, session, issue_num, clean_model, clean_effort, cli_model_args, cwd_dir, target_prompt, is_continuation)

    await manager._append_message(
        session.session_id,
        MessageRole.SYSTEM,
        "⚠️ [Interactive Desktop Terminal] Native GUI console spawning is active on Windows; headless streaming active on cloud/POSIX."
    )
    return False
