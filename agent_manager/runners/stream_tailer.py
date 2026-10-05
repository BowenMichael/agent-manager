"""
Stream Tailer Service for detached agent processes.
Asynchronously reads and processes the stream-json output log from detached agent processes.
Enables real-time websocket broadcasting and seamless state reattachment across server restarts.
"""
import os
import json
import asyncio
import logging
from pathlib import Path

import agent_manager.config as config
from agent_manager.config import MAX_SESSION_TOKENS
from agent_manager.models import AgentStatus, MessageRole
from agent_manager.runners.helpers import looks_like_quota_error
from agent_manager.runners.stream_handler import handle_tool_call_stream
from agent_manager.runners.post_turn import handle_turn_completion, handle_post_process
from agent_manager.runners.process_manager import is_process_alive, terminate_process

logger = logging.getLogger("agent_manager.runners.stream_tailer")


async def _process_stream_line(manager, session, session_id: str, line_str: str, cwd_dir: str, current_max_tokens: int) -> bool:
    """Processes a single stream JSON line. Returns True if interrupted."""
    try:
        event_obj = json.loads(line_str)
        ev = event_obj.get("event")
        if ev == "step_update":
            session.is_stalled = False
            step = event_obj.get("step_update", {})
            stype = step.get("step_type")
            sstate = step.get("state")

            usage = step.get("usage")
            if usage:
                session.input_tokens = usage.get("input_tokens", session.input_tokens)
                session.output_tokens = usage.get("output_tokens", session.output_tokens)
                session.thinking_tokens = usage.get("thinking_tokens", session.thinking_tokens)
                session.cache_read_tokens = usage.get("cache_read_tokens", session.cache_read_tokens)
                session.total_tokens = usage.get("total_tokens", session.total_tokens)
                session.token_count = session.total_tokens
                session.max_tokens = current_max_tokens
                session.quota_percent = min(100.0, round((session.total_tokens / current_max_tokens) * 100, 1))

                if getattr(config, "GUARDRAILS_ENABLED", True) and session.total_tokens >= current_max_tokens:
                    session.status = AgentStatus.PAUSED
                    session.error_message = f"Token budget limit reached ({session.total_tokens:,} / {current_max_tokens:,} tokens)."
                    if session.pid:
                        terminate_process(session.pid)
                    manager._save()
                    await manager.broadcast("session_updated", session.model_dump())
                    return True

                manager._save()
                await manager.broadcast("session_updated", session.model_dump())

            if stype == "tool":
                interrupted = await handle_tool_call_stream(manager, session, step, sstate, cwd_dir, proc=None)
                if interrupted:
                    return True
            elif stype == "agent_response":
                delta = step.get("text_delta")
                if delta:
                    await manager._broadcast_token(session_id, delta)
                if sstate == "DONE" and delta:
                    await manager._append_message(session_id, MessageRole.AGENT, delta)
        elif ev == "result":
            res_info = event_obj.get("result", {})
            final_resp = res_info.get("response", "Agent finished task.")
            final_usage = res_info.get("usage")
            if final_usage:
                session.input_tokens = final_usage.get("input_tokens", session.input_tokens)
                session.output_tokens = final_usage.get("output_tokens", session.output_tokens)
                session.thinking_tokens = final_usage.get("thinking_tokens", session.thinking_tokens)
                session.cache_read_tokens = final_usage.get("cache_read_tokens", session.cache_read_tokens)
                session.total_tokens = final_usage.get("total_tokens", session.total_tokens)
                session.token_count = session.total_tokens
            await handle_turn_completion(manager, session, final_resp)
        elif ev == "error" or event_obj.get("error"):
            err_txt = json.dumps(event_obj.get("error", event_obj))
            if looks_like_quota_error(err_txt):
                await manager._flag_quota_exceeded(session_id, err_txt)
    except json.JSONDecodeError:
        if looks_like_quota_error(line_str):
            await manager._flag_quota_exceeded(session_id, line_str)
    except Exception as json_err:
        logger.debug(f"JSON stream line parse info: {json_err}")
    return False


async def tail_agent_log(manager, session_id: str, clean_model: str = ""):
    """
    Tails the JSONL log file for the specified session, parsing events, updating session state,
    and handling process completion when the background agent terminates.
    """
    session = manager.sessions.get(session_id)
    if not session:
        return

    log_path_str = session.stream_log_file
    if not log_path_str:
        logger.warning(f"No stream_log_file specified for session {session_id}")
        return

    try:
        log_file = Path(log_path_str)
        current_max_tokens = getattr(config, "MAX_SESSION_TOKENS", MAX_SESSION_TOKENS)
        cwd_dir = session.worktree_path or getattr(config, "WORKSPACE_BASE", ".")

        # Wait up to 5 seconds for log file to be created by the spawned detached process
        for _ in range(50):
            if log_file.exists():
                break
            await asyncio.sleep(0.1)

        if not log_file.exists():
            logger.error(f"Stream log file {log_file} was not created for session {session_id}")
            session.status = AgentStatus.FAILED
            session.error_message = f"Stream log file {log_file} missing."
            manager._save()
            await manager.broadcast("session_updated", session.model_dump())
            return

        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            # Resume from saved offset if reattaching
            if session.stream_log_offset and session.stream_log_offset > 0:
                try:
                    f.seek(session.stream_log_offset)
                except Exception:
                    f.seek(0)

            while True:
                line_str = f.readline()
                if not line_str:
                    # Check if the detached background process is still running
                    alive = is_process_alive(session.pid)
                    if alive:
                        await asyncio.sleep(0.2)
                        continue

                    # Process is no longer running; drain any remaining unread content
                    remaining = f.read()
                    if remaining:
                        for extra_line in remaining.splitlines():
                            extra_clean = extra_line.strip()
                            if extra_clean:
                                interrupted = await _process_stream_line(
                                    manager, session, session_id, extra_clean, cwd_dir, current_max_tokens
                                )
                                if interrupted:
                                    return
                        session.stream_log_offset = f.tell()
                    break

                # Update offset and persist
                session.stream_log_offset = f.tell()
                line_clean = line_str.strip()
                if not line_clean:
                    continue

                interrupted = await _process_stream_line(
                    manager, session, session_id, line_clean, cwd_dir, current_max_tokens
                )
                if interrupted:
                    return

        # Process exit handling
        exit_code = 0
        if session.exit_code_file and Path(session.exit_code_file).exists():
            try:
                content = Path(session.exit_code_file).read_text(encoding="utf-8").strip()
                exit_code = int(content) if content else 0
            except Exception:
                exit_code = 0

        if exit_code != 0:
            await manager._append_message(
                session_id,
                MessageRole.SYSTEM,
                f"Agent CLI exited with code {exit_code}"
            )

        try:
            from agent_manager.telemetry import record_token_usage
            record_token_usage(
                session_id=session_id,
                repo=session.repo or "",
                model=session.model or clean_model,
                input_tokens=session.input_tokens,
                output_tokens=session.output_tokens,
                thinking_tokens=session.thinking_tokens,
                cache_read_tokens=session.cache_read_tokens,
                total_tokens=session.total_tokens
            )
        except Exception:
            pass

        await handle_post_process(manager, session, returncode=exit_code)
        manager._save()
        await manager.broadcast("session_updated", session.model_dump())
    except asyncio.CancelledError:
        if is_process_alive(session.pid):
            logger.info(f"Server restarting: Agent session {session_id} remains active in background service (PID: {session.pid}).")
        elif session.status not in [AgentStatus.COMPLETED, AgentStatus.IN_REVIEW]:
            session.status = AgentStatus.STOPPED
        manager._save()
        raise
