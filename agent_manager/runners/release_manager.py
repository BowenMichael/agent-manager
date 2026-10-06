"""
Autonomous SemVer Release Manager & Version Tagging Engine.
Parses conventional commits, calculates SemVer bumps (major, minor, patch),
updates version manifests, formats release changelog notes, and cuts annotated Git tags.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger("agent_manager.runners.release_manager")


def parse_conventional_commits(commit_messages: List[str]) -> Dict[str, Any]:
    """Parses conventional commits and determines the required SemVer bump."""
    bump = "patch"
    features, fixes, breaking, others = [], [], [], []

    for msg in commit_messages:
        clean = msg.strip()
        if not clean:
            continue
        if "BREAKING CHANGE:" in clean or re.search(r"^[a-z]+!:", clean):
            breaking.append(clean)
            bump = "major"
        elif clean.startswith("feat"):
            features.append(clean)
            if bump != "major":
                bump = "minor"
        elif clean.startswith("fix"):
            fixes.append(clean)
        else:
            others.append(clean)

    return {
        "recommended_bump": bump,
        "breaking": breaking,
        "features": features,
        "fixes": fixes,
        "others": others,
        "total_commits": len(commit_messages),
    }


def bump_semver(current_version: str, bump_type: str) -> str:
    """Computes next semantic version given bump type (major, minor, patch)."""
    # Clean version string
    raw = current_version.lstrip("v").strip()
    parts = raw.split(".")
    major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 1
    minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    else:  # patch
        return f"{major}.{minor}.{patch + 1}"


def get_project_version(root_path: Path) -> str:
    """Discovers current project version from package.json or defaults."""
    pkg_file = root_path / "package.json"
    if pkg_file.exists():
        try:
            data = json.loads(pkg_file.read_text(encoding="utf-8"))
            if "version" in data:
                return data["version"]
        except Exception:
            pass
    return "1.0.0"


def update_version_manifest(root_path: Path, new_version: str) -> bool:
    """Updates version field in package.json if present."""
    pkg_file = root_path / "package.json"
    if not pkg_file.exists():
        return False
    try:
        data = json.loads(pkg_file.read_text(encoding="utf-8"))
        data["version"] = new_version
        pkg_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        logger.warning(f"Failed to update {pkg_file}: {e}")
        return False


def generate_release_notes(version: str, parsed: Dict[str, Any]) -> str:
    """Generates structured Markdown release notes from parsed conventional commits."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [f"## Release v{version} ({date_str})", ""]

    if parsed.get("breaking"):
        lines.append("### ⚠️ Breaking Changes")
        lines.extend([f"- {b}" for b in parsed["breaking"]])
        lines.append("")
    if parsed.get("features"):
        lines.append("### 🚀 New Features")
        lines.extend([f"- {f}" for f in parsed["features"]])
        lines.append("")
    if parsed.get("fixes"):
        lines.append("### 🐛 Bug Fixes")
        lines.extend([f"- {fx}" for fx in parsed["fixes"]])
        lines.append("")
    if parsed.get("others"):
        lines.append("### 🔨 Maintenance & Improvements")
        lines.extend([f"- {o}" for o in parsed["others"][:10]])
        lines.append("")

    return "\n".join(lines).strip()


def create_annotated_git_tag(repo_path: Path, version: str, message: str) -> bool:
    """Creates a signed or annotated local Git release tag."""
    tag_name = f"v{version.lstrip('v')}"
    res = subprocess.run(
        ["git", "tag", "-a", tag_name, "-m", message],
        cwd=str(repo_path), capture_output=True, text=True, timeout=10
    )
    return res.returncode == 0
