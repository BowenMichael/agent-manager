"""
Repository Architectural Indexer & Symbol Extractor.
Extracts API routes, data models, functions, and AGENTS rules across workspace codebases.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional

IGNORED_DIRS = {
    ".git", ".worktrees", "node_modules", ".next", "dist",
    "build", "__pycache__", ".venv", "venv", ".idea", ".vscode"
}


def extract_routes(rel_path: str, content: str) -> List[Dict[str, Any]]:
    """Extracts REST endpoints from Python, TypeScript, and JavaScript files."""
    chunks = []
    seen = set()
    if rel_path.endswith(".py"):
        patterns = re.findall(r"@(?:router|app)\.(get|post|put|delete|patch)\(\s*[\"']([^\"']+)[\"']", content)
    else:
        patterns = re.findall(r"(?:app|router)\.(get|post|put|delete)\(\s*[\"']([^\"']+)[\"']", content)

    for method, path in patterns:
        key = (method.upper(), path)
        if key not in seen:
            seen.add(key)
            chunks.append({
                "type": "endpoint",
                "name": f"{method.upper()} {path}",
                "text": f"API Endpoint: {method.upper()} {path} in {rel_path}",
                "summary": f"Route handler {method.upper()} {path}",
            })
    return chunks



def extract_models(rel_path: str, content: str) -> List[Dict[str, Any]]:
    """Extracts data models, Pydantic schemas, and TypeScript interfaces."""
    chunks = []
    # Python Pydantic or SQLAlchemy classes
    py_models = re.findall(r"class\s+([A-Za-z0-9_]+)\s*\((?:BaseModel|Base|SQLModel)[^\)]*\):", content)
    for model_name in py_models:
        chunks.append({
            "type": "model",
            "name": model_name,
            "text": f"Data Model schema: {model_name} defined in {rel_path}",
            "summary": f"Schema definition for {model_name}",
        })
    # TypeScript interfaces and types
    ts_models = re.findall(r"export\s+(?:interface|type)\s+([A-Za-z0-9_]+)", content)
    for model_name in ts_models:
        chunks.append({
            "type": "model",
            "name": model_name,
            "text": f"TypeScript schema interface: {model_name} in {rel_path}",
            "summary": f"TypeScript interface {model_name}",
        })
    return chunks


def extract_rules(rel_path: str, content: str) -> List[Dict[str, Any]]:
    """Extracts sections from AGENTS.md, MANIFESTO.md, or guidelines."""
    chunks = []
    sections = re.findall(r"^(##\s+[^\n]+)\n((?:(?!^##\s+).)*)", content, re.MULTILINE | re.DOTALL)
    for header, body in sections[:8]:
        clean_header = header.replace("#", "").strip()
        body_snippet = body.strip()[:350]
        chunks.append({
            "type": "rule",
            "name": clean_header,
            "text": f"Directive rule: {clean_header}\n{body_snippet}",
            "summary": clean_header,
        })
    return chunks


def extract_symbols_from_file(repo_name: str, file_path: Path, root: Path) -> List[Dict[str, Any]]:
    """Extracts all relevant architectural chunks from a single file."""
    try:
        rel_path = file_path.relative_to(root).as_posix()
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    chunks: List[Dict[str, Any]] = []
    fname = file_path.name.lower()

    if fname in ("agents.md", "manifesto.md", "readme.md"):
        chunks.extend(extract_rules(rel_path, content))
    elif file_path.suffix in (".py", ".ts", ".tsx", ".js"):
        chunks.extend(extract_routes(rel_path, content))
        chunks.extend(extract_models(rel_path, content))

    docs = []
    for idx, c in enumerate(chunks):
        doc_id = f"{repo_name}:{rel_path}:{c['type']}:{c['name']}:{idx}"
        docs.append({
            "id": doc_id,
            "text": c["text"],
            "metadata": {
                "repo": repo_name,
                "file": rel_path,
                "type": c["type"],
                "name": c["name"],
                "summary": c["summary"],
            }
        })
    return docs


class RepoIndexer:
    """Scans and extracts architectural context from repository directories."""

    def __init__(self, extensions: Optional[List[str]] = None):
        self.extensions = set(extensions or [".py", ".ts", ".tsx", ".js", ".md", ".json"])

    def index_repo(self, repo_path: Path) -> List[Dict[str, Any]]:
        """Scans a repository and returns extracted architectural documents."""
        repo_path = repo_path.resolve()
        if not repo_path.exists():
            return []

        repo_name = repo_path.name
        extracted_docs: List[Dict[str, Any]] = []

        for p in repo_path.rglob("*"):
            if not p.is_file() or p.suffix not in self.extensions:
                continue
            if any(part in IGNORED_DIRS for part in p.parts):
                continue
            # Skip excessively large files
            try:
                if p.stat().st_size > 200_000:
                    continue
            except OSError:
                continue

            docs = extract_symbols_from_file(repo_name, p, repo_path)
            extracted_docs.extend(docs)

        return extracted_docs

    def discover_connected_repos(self, base_dir: Optional[Path] = None) -> List[Path]:
        """Discovers sibling git repositories or project roots in the workspace directory."""
        if not base_dir:
            base_dir = Path(__file__).resolve().parents[2].parent
        
        found = []
        if not base_dir.exists():
            return found

        for child in sorted(base_dir.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                if (child / ".git").exists() or (child / "package.json").exists() or (child / "pyproject.toml").exists():
                    found.append(child)
        return found
