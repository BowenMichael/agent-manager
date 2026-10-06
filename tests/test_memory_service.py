"""
Unit Tests for Semantic Vector Memory & Cross-Repository Knowledge Service.
Validates embeddings, vector search, symbol extractors, prompt injection, and API routes.
Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
"""

import tempfile
from pathlib import Path
import unittest
from fastapi.testclient import TestClient

from agent_manager.services.vector_store import (
    VectorStore, tokenize_text, embed_tokens, cosine_similarity
)
from agent_manager.services.repo_indexer import (
    RepoIndexer, extract_routes, extract_models, extract_rules
)
from agent_manager.services.memory_service import MemoryService
from agent_manager.runners.helpers import get_semantic_memory_context, get_repository_context
from agent_manager.server import app


class TestVectorStoreAndEmbeddings(unittest.TestCase):
    """Tests for vector math, feature hashing, and document similarity."""

    def test_tokenization_and_embedding(self):
        tokens = tokenize_text("def handle_webhook_event(payload: WebhookPayload):")
        self.assertIn("handle", tokens)
        self.assertIn("webhook", tokens)
        self.assertIn("event", tokens)
        self.assertIn("payload", tokens)

        vec = embed_tokens(tokens)
        self.assertEqual(len(vec), 256)
        # Verify L2 normalization
        norm = sum(x * x for x in vec)
        self.assertAlmostEqual(norm, 1.0, places=3)

    def test_cosine_similarity_ranking(self):
        v1 = embed_tokens(["auth", "login", "jwt", "token"])
        v2 = embed_tokens(["auth", "token", "session"])
        v3 = embed_tokens(["database", "postgres", "migration", "sql"])

        sim_auth = cosine_similarity(v1, v2)
        sim_db = cosine_similarity(v1, v3)
        self.assertGreater(sim_auth, sim_db)

    def test_vector_store_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            idx_file = Path(tmpdir) / "idx.json"
            store = VectorStore(idx_file)
            store.add_document("doc1", "FastAPI authentication middleware", {"repo": "agent-manager", "type": "route"})
            store.add_document("doc2", "PostgreSQL database migrations", {"repo": "fit-elo", "type": "db"})
            store.save()

            store2 = VectorStore(idx_file)
            self.assertEqual(len(store2.documents), 2)
            results = store2.search("authentication JWT middleware", top_k=1)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["id"], "doc1")


class TestRepoIndexer(unittest.TestCase):
    """Tests for extracting routes, models, and rules from files."""

    def test_extract_routes(self):
        py_code = """
@router.get("/api/sessions")
def list_sessions(): pass

@router.post("/api/sessions/{session_id}/cancel")
def cancel(): pass
"""
        routes = extract_routes("agent_manager/api/routes.py", py_code)
        self.assertEqual(len(routes), 2)
        self.assertEqual(routes[0]["name"], "GET /api/sessions")
        self.assertEqual(routes[1]["name"], "POST /api/sessions/{session_id}/cancel")

    def test_extract_models(self):
        code = """
class SessionModel(BaseModel):
    id: str

export interface ProjectConfig {
    name: string;
}
"""
        models = extract_models("models.py", code)
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0]["name"], "SessionModel")
        self.assertEqual(models[1]["name"], "ProjectConfig")

    def test_extract_rules(self):
        md = """
# Heading 1
## Sacred Worktree Isolation
Zero direct edits in main checkout. Always create worktree.

## Token Budget Guardrail
Max 15 turns before pause.
"""
        rules = extract_rules("AGENTS.md", md)
        self.assertEqual(len(rules), 2)
        self.assertIn("Sacred Worktree Isolation", rules[0]["name"])


class TestMemoryServiceAndApi(unittest.TestCase):
    """Tests for MemoryService orchestration, prompt formatting, and REST API."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.svc = MemoryService(storage_dir=Path(self.tmpdir.name))
        self.client = TestClient(app)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_indexing_and_prompt_formatting(self):
        self.svc.vector_store.add_document(
            "doc_test",
            "Relational database layer using SQLite WAL mode and SQLAlchemy.",
            {"repo": "agent-manager", "file": "agent_manager/database.py", "type": "model", "summary": "Relational DB facade"}
        )
        ctx = self.svc.format_context("How is database storage implemented?", top_k=1)
        self.assertIn("Cross-Repository Semantic Architecture Memory", ctx)
        self.assertIn("agent-manager", ctx)
        self.assertIn("agent_manager/database.py", ctx)

    def test_api_routes(self):
        # Test stats
        res = self.client.get("/api/memory/stats")
        self.assertEqual(res.status_code, 200)
        self.assertIn("total_documents", res.json())

        # Test query
        res = self.client.post("/api/memory/query", json={"query": "database session storage", "top_k": 3})
        self.assertEqual(res.status_code, 200)
        self.assertIn("results", res.json())

        # Test indexing self
        res = self.client.post("/api/memory/index", json={"index_all": False})
        self.assertEqual(res.status_code, 200)
        self.assertIn("status", res.json())


if __name__ == "__main__":
    unittest.main()
