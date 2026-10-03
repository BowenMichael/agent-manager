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
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-2.5-pro")

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

AVAILABLE_MODELS = [
    {"id": "gemini-3.8-flash-high", "name": "Gemini 3.8 Flash (High Reasoning)", "effort": "high", "type": "Antigravity Subscription"},
    {"id": "gemini-3.8-flash-medium", "name": "Gemini 3.8 Flash (Medium Reasoning)", "effort": "medium", "type": "Antigravity Subscription"},
    {"id": "gemini-3.8-flash-low", "name": "Gemini 3.8 Flash (Low / Fast)", "effort": "low", "type": "Antigravity Subscription"},
    {"id": "gemini-3.1-pro-high", "name": "Gemini 3.1 Pro (High Reasoning)", "effort": "high", "type": "Antigravity Subscription"},
    {"id": "gemini-3.1-pro-low", "name": "Gemini 3.1 Pro (Low / Fast)", "effort": "low", "type": "Antigravity Subscription"},
    {"id": "claude-sonnet-5-5-high", "name": "Claude Sonnet 5.5 (High Reasoning)", "effort": "high", "type": "Antigravity Subscription"},
    {"id": "claude-sonnet-5-5-medium", "name": "Claude Sonnet 5.5 (Medium Reasoning)", "effort": "medium", "type": "Antigravity Subscription"},
    {"id": "claude-opus-5-5-high", "name": "Claude Opus 5.5 (High Reasoning)", "effort": "high", "type": "Antigravity Subscription"},
]

DEFAULT_EFFORT = os.getenv("DEFAULT_EFFORT", "high")

AVAILABLE_EFFORT_LEVELS = [
    {"id": "low", "name": "Low (Fast turnaround, minimal thinking tokens)"},
    {"id": "medium", "name": "Medium (Balanced reasoning & speed)"},
    {"id": "high", "name": "High (Deep reasoning, thorough analysis)"},
    {"id": "xhigh", "name": "Extra High (Exhaustive chain-of-thought)"},
    {"id": "max", "name": "Max (Uncapped cognitive reasoning budget)"}
]
