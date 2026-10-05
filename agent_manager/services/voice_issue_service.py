import re
import json
import logging
import asyncio
import subprocess
from typing import Dict, Any, Optional

from agent_manager.config import AGY_CLI_PATH, GITHUB_PERSONAL_ACCESS_TOKEN, PROJECT_BOARD_IDS
from agent_manager.services.projects_service import PROJECTS_CONFIG
from agent_manager.poller.github_client import GitHubBoardClient
import httpx

logger = logging.getLogger("agent_manager.services.voice_issue")

PROJECT_KEYWORDS = {
    "fit-elo": "BowenMichael/fit-elo",
    "fitelo": "BowenMichael/fit-elo",
    "workout": "BowenMichael/fit-elo",
    "fitness": "BowenMichael/fit-elo",
    "better business deal": "BowenMichael/better_buisness_deal",
    "business deal": "BowenMichael/better_buisness_deal",
    "deal": "BowenMichael/better_buisness_deal",
    "leanfolio": "BowenMichael/leanfolio",
    "portfolio": "BowenMichael/leanfolio",
    "agent manager": "BowenMichael/agent-manager",
    "agent-manager": "BowenMichael/agent-manager",
    "manager": "BowenMichael/agent-manager",
    "f1": "BowenMichael/f1-frontend",
    "formula 1": "BowenMichael/f1-frontend",
    "telemetry": "BowenMichael/f1-frontend",
}


def infer_repo_from_text(text: str, default_repo: Optional[str] = None) -> str:
    """Infers target repository from spoken words, or returns default."""
    lower_text = text.lower()
    for kw, repo in PROJECT_KEYWORDS.items():
        if kw in lower_text:
            return repo
    return default_repo or "BowenMichael/fit-elo"


async def structure_spoken_issue(transcript: str, target_repo: Optional[str] = None) -> Dict[str, Any]:
    """Uses LLM (agy CLI) or fallback heuristics to turn raw speech into structured issue title, body, and criteria."""
    repo = target_repo or infer_repo_from_text(transcript)
    
    prompt = (
        f"You are a technical product manager. A developer spoke the following voice memo for a new task:\n\n"
        f"\"\"\"{transcript}\"\"\"\n\n"
        f"Target Repository: {repo}\n\n"
        f"Convert this spoken memo into a well-structured GitHub issue.\n"
        f"Respond ONLY with a JSON object in this exact schema (no markdown fences, no preamble):\n"
        f"{{\n"
        f'  "title": "Concise, descriptive title (under 70 chars)",\n'
        f'  "body": "Detailed Markdown description with ## Overview, ## Acceptance Criteria (bulleted checkboxes like - [ ] ...), and ## Technical Considerations"\n'
        f"}}"
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            str(AGY_CLI_PATH),
            "-p", prompt,
            "--output-format", "text",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20.0)
        out_text = stdout.decode("utf-8", errors="replace").strip()
        
        # Strip potential markdown code fences
        cleaned = re.sub(r"^```(?:json)?\s*", "", out_text, flags=re.MULTILINE)
        cleaned = re.sub(r"```$", "", cleaned, flags=re.MULTILINE).strip()
        
        data = json.loads(cleaned)
        if data.get("title") and data.get("body"):
            return {
                "repo": repo,
                "title": data["title"],
                "body": data["body"]
            }
    except Exception as e:
        logger.warning(f"LLM issue structuring failed or timed out ({e}); using intelligent heuristic fallback.")

    # High-quality heuristic fallback
    words = transcript.strip().split()
    title_words = words[:10]
    title = " ".join(title_words).capitalize()
    if len(title) > 65:
        title = title[:65] + "..."

    body = (
        f"## 📋 Overview\n"
        f"{transcript}\n\n"
        f"## ✅ Acceptance Criteria\n"
        f"- [ ] Implement core functionality described in overview\n"
        f"- [ ] Add unit tests covering standard and edge cases\n"
        f"- [ ] Update `CHANGELOG.md` in repository root\n"
        f"- [ ] Verify build and tests pass before review\n\n"
        f"---\n"
        f"*Generated via Agent Manager Voice Issue Listener*"
    )
    return {
        "repo": repo,
        "title": title,
        "body": body
    }
