import json
from typing import Any, Optional


def format_command_output(
    tool_name: str,
    raw_output: Any,
    tool_params: Optional[dict] = None
) -> str:
    """
    Format raw output from tool execution (e.g. run_command, terminal)
    into structured, readable output preserving stdout, stderr, and exit codes.
    """
    if raw_output is None:
        raw_output = ""

    # If raw_output is a string, check if it's a JSON string
    parsed_output = raw_output
    if isinstance(raw_output, str) and raw_output.strip().startswith("{") and raw_output.strip().endswith("}"):
        try:
            parsed_output = json.loads(raw_output)
        except Exception:
            parsed_output = raw_output

    if isinstance(parsed_output, dict):
        blocks = []
        exit_code = parsed_output.get("exit_code")
        if exit_code is None:
            exit_code = parsed_output.get("returncode")
        if exit_code is None:
            exit_code = parsed_output.get("status")
        if exit_code is not None:
            blocks.append(f"Exit Code: {exit_code}")

        stdout = parsed_output.get("stdout") or parsed_output.get("output")
        stderr = parsed_output.get("stderr") or parsed_output.get("error")

        if stdout and str(stdout).strip():
            blocks.append(f"[STDOUT]\n{str(stdout).strip()}")
        if stderr and str(stderr).strip():
            blocks.append(f"[STDERR]\n{str(stderr).strip()}")

        if blocks:
            return "\n\n".join(blocks)

        # Fallback to pretty-printed json if other keys exist
        try:
            return json.dumps(parsed_output, indent=2)
        except Exception:
            return str(parsed_output)

    text_out = str(raw_output).strip()
    if not text_out or text_out == "Done":
        # Empty or generic 'Done' output
        return "Command completed successfully with no output."

    return text_out
