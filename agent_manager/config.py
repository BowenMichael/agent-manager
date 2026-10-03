import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
WORKSPACE_BASE = Path(os.getenv("WORKSPACE_BASE", "e:/~Michael Bowen/Projects"))
DEFAULT_REPO = os.getenv("DEFAULT_REPO", "BowenMichael/f1-frontend")
PROJECT_BOARD_ID = os.getenv("PROJECT_BOARD_ID", "PVT_kwHOAgkA3s4Blmhh")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "15"))
MAX_ACTIVE_AGENTS = int(os.getenv("MAX_ACTIVE_AGENTS", "5"))
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-3.8-flash")
DEFAULT_EFFORT = os.getenv("DEFAULT_EFFORT", "high")

# Auto-detect GitHub PAT from environment or Antigravity MCP config
GITHUB_PERSONAL_ACCESS_TOKEN = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", "")
if not GITHUB_PERSONAL_ACCESS_TOKEN:
    mcp_path = Path.home() / ".gemini" / "config" / "mcp_config.json"
    if mcp_path.exists():
        try:
            with open(mcp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                GITHUB_PERSONAL_ACCESS_TOKEN = data.get("mcpServers", {}).get("github", {}).get("env", {}).get("GITHUB_PERSONAL_ACCESS_TOKEN", "")
        except Exception:
            pass

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

ANTIGRAVITY_IDE_CLI = Path(r"C:\Users\tv\AppData\Local\Programs\Antigravity IDE\bin\antigravity-ide.cmd")
SUBSCRIPTION_MODE = os.getenv("SUBSCRIPTION_MODE", "true").lower() in ("true", "1")

AGY_CLI_PATH = Path(os.environ.get("LOCALAPPDATA", r"C:\Users\tv\AppData\Local")) / "agy" / "bin" / "agy.exe"

# Antigravity CLI Execution Mode: 'terminal' (Default Option 1) or 'web_stream' (Override Option 2)
AGY_MODE = os.getenv("AGY_MODE", "terminal").lower()

MAX_SESSION_TOKENS = int(os.getenv("MAX_SESSION_TOKENS", "150000"))
COMPACT_COMPLETED_CHAT = os.getenv("COMPACT_COMPLETED_CHAT", "true").lower() in ("true", "1", "yes")

AVAILABLE_MODELS = [
    {"id": "gemini-3.8-flash", "name": "Gemini 3.8 Flash (Recommended)", "type": "Antigravity Subscription"},
    {"id": "gemini-3.7-flash", "name": "Gemini 3.7 Flash", "type": "Antigravity Subscription"},
    {"id": "gemini-3.6-flash", "name": "Gemini 3.6 Flash", "type": "Antigravity Subscription"},
    {"id": "gemini-3.1-pro", "name": "Gemini 3.1 Pro (Advanced Reasoning)", "type": "Antigravity Subscription"},
    {"id": "claude-sonnet-5-5", "name": "Claude Sonnet 5.5", "type": "Antigravity Subscription"},
    {"id": "claude-opus-5-5", "name": "Claude Opus 5.5", "type": "Antigravity Subscription"},
    {"id": "gpt-oss-120b", "name": "GPT-OSS 120B", "type": "Antigravity Subscription"},
]

AVAILABLE_EFFORT_LEVELS = [
    {"id": "low", "name": "Low (Fast turnaround, minimal thinking tokens)"},
    {"id": "medium", "name": "Medium (Balanced reasoning & speed)"},
    {"id": "high", "name": "High (Deep reasoning, thorough analysis)"},
    {"id": "xhigh", "name": "Extra High (Exhaustive chain-of-thought)"},
    {"id": "max", "name": "Max (Uncapped cognitive reasoning budget)"}
]

def resolve_model_and_effort(model: str = None, effort: str = None) -> tuple[str, str, list[str]]:
    """
    Normalizes model and effort flags for Antigravity CLI (agy).
    Strips conflicting effort suffixes from model name if effort is explicitly provided.
    Returns: (normalized_model, normalized_effort, cli_args_list)
    """
    import re
    current_default_model = globals().get("DEFAULT_MODEL", "gemini-3.8-flash")
    current_default_effort = globals().get("DEFAULT_EFFORT", "high")

    m = (model or current_default_model or "gemini-3.8-flash").strip()
    e = (effort or current_default_effort or "high").strip().lower()

    valid_efforts = {"low", "medium", "high", "xhigh", "max"}
    if e not in valid_efforts:
        e = "high"

    # If model has a suffix like -high, -medium, -low, strip it when passing with --effort
    base_model = re.sub(r'-(low|medium|high|xhigh|max)$', '', m)

    cli_args = ["--model", base_model, "--effort", e]
    return base_model, e, cli_args

CLI_SETTINGS_PATH = Path.home() / ".gemini" / "antigravity-cli" / "settings.json"

def get_cli_overage_credits() -> bool:
    """Reads whether AI Credit Overages (useG1Credits) are enabled in CLI settings."""
    try:
        if CLI_SETTINGS_PATH.exists():
            with open(CLI_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return bool(data.get("useG1Credits", False))
    except Exception:
        pass
    return False

def set_cli_overage_credits(allow: bool) -> bool:
    """Configures AI Credit Overages (useG1Credits) in ~/.gemini/antigravity-cli/settings.json."""
    try:
        CLI_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if CLI_SETTINGS_PATH.exists():
            try:
                with open(CLI_SETTINGS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data["useG1Credits"] = bool(allow)
        with open(CLI_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False

# All GitHub Project boards to watch (comma-separated). Defaults to F1 board + Agent Manager board.
PROJECT_BOARD_IDS = [
    p.strip() for p in os.getenv(
        "PROJECT_BOARD_IDS",
        f"{PROJECT_BOARD_ID},PVT_kwHOAgkA3s4BlnSi"
    ).split(",") if p.strip()
]
