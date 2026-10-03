import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
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
