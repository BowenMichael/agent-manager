"""
Semantic Memory & Cross-Repository Knowledge Service.
Coordinates VectorStore and RepoIndexer to index, query, and inject cross-repository
architectural context into agent planning stages.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from agent_manager.services.vector_store import VectorStore
from agent_manager.services.repo_indexer import RepoIndexer

_GLOBAL_MEMORY_SERVICE: Optional["MemoryService"] = None


class MemoryService:
    """High-level semantic vector memory and cross-repository intelligence orchestrator."""

    def __init__(self, storage_dir: Optional[Path] = None):
        if not storage_dir:
            repo_root = Path(__file__).resolve().parents[2]
            storage_dir = repo_root / "data" / "memory"
        self.storage_dir = storage_dir
        self.index_path = self.storage_dir / "vector_index.json"
        self.vector_store = VectorStore(self.index_path)
        self.indexer = RepoIndexer()

    def index_repository(self, repo_path: Union[str, Path]) -> int:
        """Indexes symbols, routes, models, and rules from a single repository."""
        p = Path(repo_path)
        docs = self.indexer.index_repo(p)
        count = self.vector_store.add_documents(docs)
        self.vector_store.save()
        return count

    def index_connected_repositories(self, base_dir: Optional[Union[str, Path]] = None) -> Dict[str, int]:
        """Discovers and indexes all connected repositories in the workspace parent directory."""
        bd = Path(base_dir) if base_dir else None
        repos = self.indexer.discover_connected_repos(bd)
        results: Dict[str, int] = {}
        for r in repos:
            count = self.index_repository(r)
            results[r.name] = count
        return results

    def query(
        self, query_text: str, top_k: int = 5, repo: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Searches indexed architectural memory for relevant context."""
        return self.vector_store.search(query_text, top_k=top_k, repo_filter=repo)

    def format_context(
        self, query_text: str, top_k: int = 3, repo: Optional[str] = None
    ) -> str:
        """Formats top retrieved context items into markdown for prompt injection."""
        results = self.query(query_text, top_k=top_k, repo=repo)
        if not results:
            return ""

        lines = ["### 🌐 Cross-Repository Semantic Architecture Memory", ""]
        for idx, item in enumerate(results, 1):
            meta = item.get("metadata", {})
            repo_name = meta.get("repo", "workspace")
            file_name = meta.get("file", "unknown")
            item_type = meta.get("type", "symbol")
            summary = meta.get("summary", meta.get("name", ""))
            score = item.get("score", 0.0)

            lines.append(f"{idx}. **[{repo_name}]** `{file_name}` ({item_type} - sim {score}):")
            lines.append(f"   > {summary}")
        lines.append("")
        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """Returns statistics on currently indexed memory."""
        return {
            "total_documents": len(self.vector_store.documents),
            "indexed_repos": self.vector_store.get_indexed_repos(),
            "storage_path": str(self.index_path),
            "status": "ready" if len(self.vector_store.documents) > 0 else "empty",
        }

    def clear(self) -> None:
        """Wipes the vector memory index."""
        self.vector_store.clear()


def get_memory_service(storage_dir: Optional[Path] = None) -> MemoryService:
    """Returns singleton instance of MemoryService."""
    global _GLOBAL_MEMORY_SERVICE
    if _GLOBAL_MEMORY_SERVICE is None:
        _GLOBAL_MEMORY_SERVICE = MemoryService(storage_dir=storage_dir)
    return _GLOBAL_MEMORY_SERVICE
