"""
Long Generated File & Binary Asset Filter Service.
Prevents agents and context engines from reading bloated lockfiles,
minified assets, source maps, binary dumps, and non-sliced monoliths.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import logging
from pathlib import Path
from typing import Tuple, List, Union, Set

logger = logging.getLogger("agent_manager.services.file_filter")

GENERATED_FILENAMES: Set[str] = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "cargo.lock",
    "poetry.lock",
    "gemfile.lock",
    "composer.lock",
    "pipfile.lock",
}

GENERATED_SUFFIXES: Set[str] = {
    ".min.js",
    ".min.css",
    ".map",
    ".wasm",
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".dylib",
    ".exe",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".csv",
}

IGNORED_DIRECTORIES: Set[str] = {
    "node_modules",
    "dist",
    "build",
    ".next",
    ".turbo",
    "coverage",
    ".git",
    ".worktrees",
    ".venv",
    "venv",
    "__pycache__",
}


def is_in_ignored_directory(path: Path) -> bool:
    """Checks if the path resides inside an ignored directory."""
    parts = {p.lower() for p in path.parts}
    return bool(parts & IGNORED_DIRECTORIES)


def is_generated_or_binary(file_path: Union[str, Path]) -> Tuple[bool, str]:
    """
    Checks if a file is a lockfile, minified asset, binary file, or build artifact.
    Returns (True, reason) if it should be skipped.
    """
    path = Path(file_path)
    name_lower = path.name.lower()

    if is_in_ignored_directory(path):
        return True, f"File resides in ignored directory (build/vendor/cache)"

    if name_lower in GENERATED_FILENAMES:
        return True, f"File is a dependency lockfile ({path.name})"

    for suffix in GENERATED_SUFFIXES:
        if name_lower.endswith(suffix):
            return True, f"File has generated or binary suffix ({suffix})"

    return False, ""


def is_file_too_large_for_inspection(
    file_path: Union[str, Path],
    max_lines: int = 250
) -> Tuple[bool, str]:
    """
    Checks if an existing text file exceeds max_lines, requiring sliced viewing.
    """
    path = Path(file_path)
    if not path.is_file():
        return False, ""

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            count = sum(1 for _ in f)
        if count > max_lines:
            return True, f"File has {count} lines, exceeding safe limit ({max_lines} LOC). Use sliced line inspection."
    except Exception as e:
        logger.warning(f"Error checking line count for {path}: {e}")

    return False, ""


def filter_safe_source_files(file_paths: List[Union[str, Path]]) -> List[str]:
    """Filters a list of file paths, removing generated, binary, and lockfiles."""
    safe = []
    for p in file_paths:
        should_skip, _ = is_generated_or_binary(p)
        if not should_skip:
            safe.append(str(p))
    return safe
