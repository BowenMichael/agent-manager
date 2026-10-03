import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
GITHUB_PERSONAL_ACCESS_TOKEN = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", "")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
WORKSPACE_BASE = Path(os.getenv("WORKSPACE_BASE", "e:/~Michael Bowen/Projects"))
DEFAULT_REPO = os.getenv("DEFAULT_REPO", "BowenMichael/f1-frontend")
MAX_ACTIVE_AGENTS = int(os.getenv("MAX_ACTIVE_AGENTS", "5"))
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-2.5-pro")

# Base directory for the agent manager package
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
