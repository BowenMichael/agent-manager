import re
from typing import Optional

# Project Board V2 Field and Option IDs (F1 Viewer Sprint Board)
STATUS_FIELD_ID = "PVTSSF_lAHOAgkA3s4BlmhhzhkSuu0"
STATUS_NAMES = {
    "backlog": "📥 Backlog",
    "ready": "📋 Ready for Agent",
    "in_progress": "⚡ In Progress",
    "in_review": "🔍 In Review",
    "done": "✅ Done",
}
STATUS_OPTIONS = {
    "backlog": "3abe26ce",      # 📥 Backlog
    "ready": "8b88d8d3",        # 📋 Ready for Agent
    "in_progress": "0855f60f",  # ⚡ In Progress
    "in_review": "14cfb9b7",    # 🔍 In Review
    "done": "b167c286"          # ✅ Done
}


def is_empty_or_template_only(body: Optional[str]) -> bool:
    """Detects if an issue body contains only template boilerplate or empty comments."""
    if not body or not body.strip():
        return True
    # Strip markdown comments <!-- ... -->
    cleaned = re.sub(r'<!--.*?-->', '', body, flags=re.DOTALL)
    # Strip markdown headers, checkboxes, and standard template section titles
    cleaned = re.sub(r'#+\s*', '', cleaned)
    cleaned = re.sub(r'-\s*\[\s*\]\s*Criterion\s*\d+', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'-\s*\[\s*\]\s*', '', cleaned)
    cleaned = re.sub(r'(Objective|Acceptance Criteria|Requirements|Description|Context):?', '', cleaned, flags=re.IGNORECASE)
    return len(cleaned.strip()) < 15
