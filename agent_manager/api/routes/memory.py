"""
Memory & Semantic Intelligence API Routes.
Exposes semantic vector search, repo indexing triggers, and cross-repo stats.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agent_manager.services.memory_service import get_memory_service

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Semantic search query text")
    top_k: int = Field(default=5, ge=1, le=50, description="Maximum number of context chunks to return")
    repo: Optional[str] = Field(default=None, description="Optional repo filter")


class MemoryIndexRequest(BaseModel):
    repo_path: Optional[str] = Field(default=None, description="Specific repository path to index")
    index_all: bool = Field(default=False, description="Index all sibling connected workspaces")


@router.post("/query")
def query_semantic_memory(payload: MemoryQueryRequest):
    """Searches cross-repository vector memory for relevant architectural context."""
    svc = get_memory_service()
    try:
        results = svc.query(payload.query, top_k=payload.top_k, repo=payload.repo)
        return {
            "query": payload.query,
            "count": len(results),
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Memory search failed: {str(e)}")


@router.post("/index")
def trigger_indexing(payload: MemoryIndexRequest):
    """Triggers indexing of a specific repository or all connected workspaces."""
    svc = get_memory_service()
    try:
        if payload.index_all:
            results = svc.index_connected_repositories()
            return {"status": "indexed_all", "summary": results}
        elif payload.repo_path:
            count = svc.index_repository(payload.repo_path)
            return {"status": "indexed_repo", "chunks_indexed": count, "path": payload.repo_path}
        else:
            # Default to indexing current project root
            from pathlib import Path
            root = Path(__file__).resolve().parents[3]
            count = svc.index_repository(root)
            return {"status": "indexed_self", "chunks_indexed": count, "path": str(root)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")


@router.get("/stats")
def get_memory_statistics():
    """Returns vector memory statistics and indexed repository list."""
    svc = get_memory_service()
    return svc.get_stats()
