import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"
_saved_settings = {}
if SETTINGS_FILE.exists():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as _f:
            _saved_settings = json.load(_f) or {}
    except Exception:
        pass

PORT = int(_saved_settings.get("PORT") or os.getenv("PORT", "8000"))
HOST = _saved_settings.get("HOST") or os.getenv("HOST", "0.0.0.0")
GITHUB_WEBHOOK_SECRET = _saved_settings.get("GITHUB_WEBHOOK_SECRET") or os.getenv("GITHUB_WEBHOOK_SECRET", "")
GEMINI_API_KEY = _saved_settings.get("gemini_api_key") or _saved_settings.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY", "")
WORKSPACE_BASE = Path(_saved_settings.get("WORKSPACE_BASE") or os.getenv("WORKSPACE_BASE", "e:/~Michael Bowen/Projects"))
DEFAULT_REPO = _saved_settings.get("default_repo") or _saved_settings.get("DEFAULT_REPO") or os.getenv("DEFAULT_REPO", "BowenMichael/f1-frontend")
PROJECT_BOARD_ID = _saved_settings.get("project_board_id") or _saved_settings.get("PROJECT_BOARD_ID") or os.getenv("PROJECT_BOARD_ID", "PVT_kwHOAgkA3s4Blmhh")
POLL_INTERVAL_SECONDS = int(_saved_settings.get("poll_interval_seconds") or _saved_settings.get("POLL_INTERVAL_SECONDS") or os.getenv("POLL_INTERVAL_SECONDS", "15"))
MAX_ACTIVE_AGENTS = int(_saved_settings.get("max_active_agents") or _saved_settings.get("MAX_ACTIVE_AGENTS") or os.getenv("MAX_ACTIVE_AGENTS", "5"))
DEFAULT_MODEL = _saved_settings.get("default_model") or _saved_settings.get("DEFAULT_MODEL") or os.getenv("DEFAULT_MODEL", "gemini-3.8-flash")
DEFAULT_EFFORT = (_saved_settings.get("effort_level") or _saved_settings.get("default_effort") or os.getenv("DEFAULT_EFFORT", "high")).lower()

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

# Antigravity CLI Execution Mode: 'web_stream' (Default) or 'terminal' (Desktop Window)
AGY_MODE = (_saved_settings.get("agy_mode") or os.getenv("AGY_MODE", "web_stream")).lower()

IS_SERVER = (_saved_settings.get("is_server") if "is_server" in _saved_settings else os.getenv("IS_SERVER", "false").lower() in ("true", "1", "yes"))
CLI_IDLE_TIMEOUT_MINUTES = int(_saved_settings.get("cli_idle_timeout_minutes") or os.getenv("CLI_IDLE_TIMEOUT_MINUTES", "30"))

MAX_SESSION_TOKENS = int(_saved_settings.get("max_session_tokens") or os.getenv("MAX_SESSION_TOKENS", "150000"))
COMPACT_COMPLETED_CHAT = _saved_settings.get("compact_completed_chat") if "compact_completed_chat" in _saved_settings else (os.getenv("COMPACT_COMPLETED_CHAT", "true").lower() in ("true", "1", "yes"))

# Circuit Breaker & Turn Budget Guardrails
GUARDRAILS_ENABLED = _saved_settings.get("guardrails_enabled") if "guardrails_enabled" in _saved_settings else (os.getenv("GUARDRAILS_ENABLED", "true").lower() in ("true", "1", "yes"))
AUTO_MERGE_ENABLED = _saved_settings.get("auto_merge_enabled") if "auto_merge_enabled" in _saved_settings else (os.getenv("AUTO_MERGE_ENABLED", "false").lower() in ("true", "1", "yes"))
MAX_TURNS_PER_SESSION = int(_saved_settings.get("max_turns_per_session") or os.getenv("MAX_TURNS_PER_SESSION", "15"))
CIRCUIT_BREAKER_DUPLICATE_THRESHOLD = int(_saved_settings.get("circuit_breaker_duplicate_threshold") or os.getenv("CIRCUIT_BREAKER_DUPLICATE_THRESHOLD", "3"))
CIRCUIT_BREAKER_MAX_CONSECUTIVE_READS = int(_saved_settings.get("circuit_breaker_max_consecutive_reads") or os.getenv("CIRCUIT_BREAKER_MAX_CONSECUTIVE_READS", "8"))

# Multi-stage Workflow Pipeline (Issue #36: dumb model summary -> smart model planning -> dumb model implementation)
WORKFLOW_PIPELINE_ENABLED = _saved_settings.get("workflow_pipeline_enabled") if "workflow_pipeline_enabled" in _saved_settings else (os.getenv("WORKFLOW_PIPELINE_ENABLED", "false").lower() in ("true", "1", "yes"))
PIPELINE_SUMMARY_MODEL = _saved_settings.get("pipeline_summary_model") or os.getenv("PIPELINE_SUMMARY_MODEL", "gemini-3.8-flash")
PIPELINE_SUMMARY_EFFORT = (_saved_settings.get("pipeline_summary_effort") or os.getenv("PIPELINE_SUMMARY_EFFORT", "low")).lower()
PIPELINE_PLANNING_MODEL = _saved_settings.get("pipeline_planning_model") or os.getenv("PIPELINE_PLANNING_MODEL", "gemini-3.1-pro")
PIPELINE_PLANNING_EFFORT = (_saved_settings.get("pipeline_planning_effort") or os.getenv("PIPELINE_PLANNING_EFFORT", "high")).lower()
PIPELINE_IMPLEMENTATION_MODEL = _saved_settings.get("pipeline_implementation_model") or os.getenv("PIPELINE_IMPLEMENTATION_MODEL", "gemini-3.8-flash")
PIPELINE_IMPLEMENTATION_EFFORT = (_saved_settings.get("pipeline_implementation_effort") or os.getenv("PIPELINE_IMPLEMENTATION_EFFORT", "low")).lower()

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
