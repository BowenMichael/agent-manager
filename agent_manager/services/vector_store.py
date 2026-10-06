"""
Vector Store & Semantic Embedding Engine.
Provides lightweight, zero-dependency token and subword hashed vector embeddings,
cosine similarity nearest-neighbor search, and persistent storage.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import json
import math
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

VECTOR_DIM = 256


def tokenize_text(text: str) -> List[str]:
    """Tokenizes text into words, code symbols, camelCase, and snake_case tokens."""
    tokens = []
    # Split camelCase and identifiers
    cleaned = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    raw_words = re.findall(r"[A-Za-z0-9_]+", cleaned)
    for w in raw_words:
        w_lower = w.lower()
        tokens.append(w_lower)
        subparts = w_lower.split("_")
        if len(subparts) > 1:
            tokens.extend([sp for sp in subparts if len(sp) > 1])
    return tokens


def embed_tokens(tokens: List[str], dim: int = VECTOR_DIM) -> List[float]:
    """Generates a dense unit-normalized embedding vector using deterministic feature hashing."""
    vec = [0.0] * dim
    if not tokens:
        return vec

    for token in tokens:
        # Compute primary hash and secondary sign hash
        h = hash(token)
        idx = abs(h) % dim
        sign = 1.0 if (abs(h >> 8) % 2 == 0) else -1.0
        # Weight by length/uniqueness heuristic
        weight = 1.0 + math.log1p(len(token))
        vec[idx] += sign * weight

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 1e-9:
        vec = [v / norm for v in vec]
    return vec


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Computes cosine similarity between two unit-normalized vectors."""
    if len(v1) != len(v2) or not v1:
        return 0.0
    return sum(a * b for a, b in zip(v1, v2))


class VectorStore:
    """Lightweight vector store with JSON persistence and cosine search."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path
        self.documents: Dict[str, Dict[str, Any]] = {}
        if storage_path and storage_path.exists():
            self.load()

    def add_document(self, doc_id: str, text: str, metadata: Dict[str, Any]) -> None:
        """Embeds and indexes a single document."""
        tokens = tokenize_text(text + " " + metadata.get("title", "") + " " + metadata.get("name", ""))
        vector = embed_tokens(tokens)
        self.documents[doc_id] = {
            "id": doc_id,
            "text": text,
            "metadata": metadata,
            "vector": vector,
        }

    def add_documents(self, docs: List[Dict[str, Any]]) -> int:
        """Batch indexes multiple documents."""
        count = 0
        for doc in docs:
            doc_id = doc.get("id") or str(len(self.documents) + 1)
            text = doc.get("text", "")
            metadata = doc.get("metadata", {})
            self.add_document(doc_id, text, metadata)
            count += 1
        return count

    def search(
        self, query: str, top_k: int = 5, repo_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Finds top-k most similar documents to the query using cosine similarity."""
        if not self.documents:
            return []

        q_tokens = tokenize_text(query)
        q_vec = embed_tokens(q_tokens)

        scored: List[Tuple[float, Dict[str, Any]]] = []
        for doc in self.documents.values():
            if repo_filter and doc["metadata"].get("repo") != repo_filter:
                continue
            sim = cosine_similarity(q_vec, doc["vector"])
            scored.append((sim, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for sim, doc in scored[:top_k]:
            results.append({
                "id": doc["id"],
                "score": round(sim, 4),
                "metadata": doc["metadata"],
                "text": doc["text"][:600],
            })
        return results

    def save(self) -> None:
        """Persists index to disk."""
        if not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "count": len(self.documents),
            "documents": self.documents,
        }
        self.storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self) -> None:
        """Loads index from disk."""
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            self.documents = data.get("documents", {})
        except Exception:
            self.documents = {}

    def clear(self) -> None:
        """Clears all indexed documents."""
        self.documents.clear()
        if self.storage_path and self.storage_path.exists():
            try:
                self.storage_path.unlink()
            except Exception:
                pass

    def get_indexed_repos(self) -> List[str]:
        """Returns unique repository names currently indexed."""
        repos = set()
        for doc in self.documents.values():
            repo = doc.get("metadata", {}).get("repo")
            if repo:
                repos.add(repo)
        return sorted(list(repos))
