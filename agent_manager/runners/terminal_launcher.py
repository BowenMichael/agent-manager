import subprocess
from pathlib import Path
from datetime import datetime
from agent_manager.models import MessageRole, AgentStatus
from agent_manager.config import AGY_CLI_PATH

subprocess_create_new_console = 0x00000010


async def launch_desktop_terminal(manager, session, issue_num: int, clean_model: str, clean_effort: str, cli_model_args: list, cwd_dir: str, target_prompt: str, is_continuation: bool):
    title_str = f"Antigravity CLI (agy) - Issue #{issue_num} [{clean_model} / {clean_effort}]"
    launcher_path = Path(cwd_dir) / ".agy_terminal_launch.ps1"
    safe_prompt = target_prompt.replace('@"', '`@"').replace('"@', '`"@')
    continue_flag = "--continue" if is_continuation else ""

    script_lines = [
        "$OutputEncoding = [System.Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()",
        f"$host.ui.RawUI.WindowTitle = '{title_str}'",
        f"Write-Host '🚀 Launching Antigravity CLI for Issue #{issue_num} [{clean_model}]...' -ForegroundColor Cyan",
        "$promptText = @\"",
        safe_prompt,
        "\"@",
        f"& \"{AGY_CLI_PATH}\" {' '.join(cli_model_args)} {continue_flag} --dangerously-skip-permissions -i $promptText"
    ]
    launcher_path.write_text("\n".join(script_lines), encoding="utf-8")
    session.terminal_command = f'& "{AGY_CLI_PATH}" {" ".join(cli_model_args)} {continue_flag} --dangerously-skip-permissions -i "{target_prompt[:80]}..."'

    await manager._append_message(
        session.session_id,
        MessageRole.SYSTEM,
        f"🚀 [Option 1: Interactive Desktop Terminal] Spawning Antigravity CLI session in dedicated PowerShell window at: {cwd_dir}\n"
        f"Model: {clean_model} • Effort: {clean_effort}"
    )
    session.last_activity_at = datetime.utcnow().isoformat()
    manager._save()
    await manager.broadcast("session_updated", session.model_dump())

    proc = subprocess.Popen(
        ["powershell.exe", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", str(launcher_path)],
        cwd=str(cwd_dir),
        creationflags=subprocess_create_new_console
    )
    manager._active_agents[session.session_id] = proc
    session.status = AgentStatus.IN_REVIEW
    manager._save()
    await manager.broadcast("session_updated", session.model_dump())
