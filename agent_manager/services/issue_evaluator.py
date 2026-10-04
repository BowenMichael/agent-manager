import re
from typing import Optional

AGENT_INTERPRETATION_HEADER = "### 🤖 Agent Interpretation & Requirements Breakdown"


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
    cleaned = re.sub(
        r'(Objective|Acceptance Criteria|Requirements|Description|Context|Notes|Visual Verification Required|Screenshot or UI demonstration|Test output / CLI recording):?',
        '',
        cleaned,
        flags=re.IGNORECASE
    )
    # Strip emoji characters commonly found in the issue template
    cleaned = re.sub(r'[\U00010000-\U0010ffff]|[\u2600-\u27ff]|[\u2300-\u23ff]|[\u2b50-\u2b55]|[\ufe00-\ufe0f]', '', cleaned)
    return len(cleaned.strip()) < 15


def is_sparse_issue(body: Optional[str]) -> bool:
    """
    Determines if an issue description is sparse or title-only.
    True if:
    - None or empty whitespace
    - Contains only template boilerplate (via is_empty_or_template_only)
    - Stripped content without markdown headers/structure is less than 50 characters
    """
    if is_empty_or_template_only(body):
        return True

    # Strip markdown comments, headers, bullets, template words, and emojis
    cleaned = re.sub(r'<!--.*?-->', '', body or '', flags=re.DOTALL)
    cleaned = re.sub(r'#+\s*', '', cleaned)
    cleaned = re.sub(r'-\s*\[\s*\]\s*', '', cleaned)
    cleaned = re.sub(
        r'(Objective|Acceptance Criteria|Requirements|Description|Context|Notes|Visual Verification Required|Screenshot or UI demonstration|Test output / CLI recording):?',
        '',
        cleaned,
        flags=re.IGNORECASE
    )
    cleaned = re.sub(r'[\*\-_`\(\)]', '', cleaned)
    cleaned = re.sub(r'[\U00010000-\U0010ffff]|[\u2600-\u27ff]|[\u2300-\u23ff]|[\u2b50-\u2b55]|[\ufe00-\ufe0f]', '', cleaned)
    return len(cleaned.strip()) < 50
