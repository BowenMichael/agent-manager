import json
import asyncio
import logging
from datetime import datetime
from agent_manager.models import MessageRole

logger = logging.getLogger("agent_manager.runners.cli_turn")


async def run_cli_turn(manager, session_id: str, prompt: str, cwd_dir: str, model: str, effort: str) -> str:
    """Runs a single prompt turn via Antigravity CLI and returns the generated text response."""
    from agent_manager.config import AGY_CLI_PATH, resolve_model_and_effort
    session = manager.sessions[session_id]
    clean_model, clean_effort, cli_model_args = resolve_model_and_effort(model, effort)
    cmd_args = [
        str(AGY_CLI_PATH),
        *cli_model_args,
        "--dangerously-skip-permissions",
        "--output-format", "stream-json",
        "-p", prompt
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd_args,
        cwd=str(cwd_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    manager._active_agents[session_id] = proc
    accumulated_text = []
    accumulated_thought = []

    while True:
        line_bytes = await proc.stdout.readline()
        if not line_bytes:
            break
        line_str = line_bytes.decode('utf-8', errors='replace').strip()
        if not line_str:
            continue
        try:
            event_obj = json.loads(line_str)
            ev = event_obj.get("event")
            if ev == "step_update":
                step = event_obj.get("step_update", {})
                stype = step.get("step_type")

                # Live Token Usage
                usage = step.get("usage")
                if usage:
                    session.input_tokens = usage.get("input_tokens", session.input_tokens)
                    session.output_tokens = usage.get("output_tokens", session.output_tokens)
                    session.thinking_tokens = usage.get("thinking_tokens", session.thinking_tokens)
                    session.total_tokens = usage.get("total_tokens", session.total_tokens)
                    session.token_count = session.total_tokens
                    manager._save()
                    await manager.broadcast("session_updated", session.model_dump())

                if stype == "thought":
                    delta = step.get("text_delta")
                    if delta:
                        accumulated_thought.append(delta)
                        await manager.broadcast("thought_delta", {
                            "session_id": session_id,
                            "delta": delta,
                            "model": clean_model
                        })
                        session.last_activity_at = datetime.utcnow().isoformat()
                        session.is_stalled = False
                        if len(accumulated_thought) % 12 == 1:
                            recent_thought = "".join(accumulated_thought).strip()[-80:].replace("\n", " ")
                            session.current_activity = f"Planning ({clean_model}): {recent_thought}..."
                            await manager.broadcast("session_updated", session.model_dump())

                elif stype == "agent_response":
                    delta = step.get("text_delta")
                    if delta:
                        accumulated_text.append(delta)
                        await manager._broadcast_token(session_id, delta)

            elif ev == "result":
                res_info = event_obj.get("result", {})
                final_txt = res_info.get("response")
                if final_txt:
                    accumulated_text = [final_txt]
                final_usage = res_info.get("usage")
                if final_usage:
                    session.input_tokens = final_usage.get("input_tokens", session.input_tokens)
                    session.output_tokens = final_usage.get("output_tokens", session.output_tokens)
                    session.thinking_tokens = final_usage.get("thinking_tokens", session.thinking_tokens)
                    session.total_tokens = final_usage.get("total_tokens", session.total_tokens)
                    session.token_count = session.total_tokens
        except Exception:
            pass

    await proc.wait()
    manager._active_agents.pop(session_id, None)

    try:
        from agent_manager.telemetry import record_token_usage
        record_token_usage(
            session_id=session_id,
            repo=session.repo or "",
            model=clean_model,
            input_tokens=session.input_tokens,
            output_tokens=session.output_tokens,
            thinking_tokens=session.thinking_tokens,
            cache_read_tokens=session.cache_read_tokens,
            total_tokens=session.total_tokens
        )
    except Exception as tel_err:
        logger.debug(f"Telemetry record error in cli turn: {tel_err}")

    if accumulated_thought:
        full_thought = "".join(accumulated_thought).strip()
        if full_thought:
            await manager._append_message(session_id, MessageRole.THOUGHT, full_thought)

    return "".join(accumulated_text).strip()
