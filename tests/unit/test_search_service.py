"""Unit tests for SearchService.

Uses a FakeChunkRepository (in-memory) and a MockEmbedder to verify:
  1. embed_query() is called with the raw query string.
  2. Empty repository results return an empty list without error.
  3. Unexpected repository exceptions are wrapped in SearchFailedError.

No real DB, no real HuggingFace model — these run fast and offline.
"""

import pytest
from typing import List, Optional

from app.domain.exceptions import SearchFailedError
from app.domain.interfaces.document_chunk_repository import DocumentChunkRepositoryInterface
from app.domain.models.document_chunk import DocumentChunk
from app.domain.models.search_result import SearchResult
from app.services.search_service import SearchService


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class FakeChunkRepository(DocumentChunkRepositoryInterface):
    """In-memory chunk repository for search tests."""

    def __init__(self, search_results: Optional[List[SearchResult]] = None):
        # Pre-seeded results returned by search_similar.
        self._search_results = search_results or []

    def save_many(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        return chunks

    def list_by_document(self, document_id: str) -> List[DocumentChunk]:
        return []

    def delete_by_document_id(self, document_id: str) -> None:
        pass

    def search_similar(
        self,
        query_embedding: List[float],
        top_k: int,
        user_id: Optional[str] = None,
    ) -> List[SearchResult]:
        # Record last call for assertion
        self.last_query_embedding = query_embedding
        self.last_top_k = top_k
        self.last_user_id = user_id
        return self._search_results


class FailingChunkRepository(DocumentChunkRepositoryInterface):
    """Repository that always raises on search_similar."""

    def save_many(self, chunks): return chunks
    def list_by_document(self, document_id): return []
    def delete_by_document_id(self, document_id): pass

    def search_similar(self, query_embedding, top_k, user_id=None):
        raise RuntimeError("Simulated pgvector failure")


class MockEmbedder:
    """Records embed_query calls and returns a deterministic dummy vector."""

    def __init__(self):
        self.embed_query_calls: List[str] = []

    def embed_query(self, text: str) -> List[float]:
        self.embed_query_calls.append(text)
        return [0.5] * 384


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_chunk(document_id: str = "doc-1", chunk_text: str = "hello") -> DocumentChunk:
    return DocumentChunk(
        document_id=document_id,
        chunk_text=chunk_text,
        chunk_index=0,
        metadata={"section": "intro"},
    )


def _make_result(chunk: DocumentChunk, score: float = 0.9) -> SearchResult:
    return SearchResult(chunk=chunk, similarity_score=score, file_name="test.pdf")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSearchServiceEmbedQuery:
    """embed_query() must be called with the raw query string."""

    def test_embed_query_called_with_raw_query(self):
        embedder = MockEmbedder()
        chunk = _make_chunk()
        repo = FakeChunkRepository(search_results=[_make_result(chunk)])
        service = SearchService(chunk_repository=repo, embedder=embedder)

        service.search(query="acne treatment", top_k=5)

        assert len(embedder.embed_query_calls) == 1
        assert embedder.embed_query_calls[0] == "acne treatment"

    def test_embed_query_not_embed_passages(self):
        """SearchService must call embed_query, never embed_passages."""
        embedder = MockEmbedder()
        # embed_passages does not exist on MockEmbedder intentionally —
        # if SearchService tried to call it, it would AttributeError.
        repo = FakeChunkRepository()
        service = SearchService(chunk_repository=repo, embedder=embedder)

        service.search(query="test query", top_k=3)

        # embed_query was called exactly once, meaning embed_passages was NOT called.
        assert len(embedder.embed_query_calls) == 1


class TestSearchServiceResults:
    """Result mapping and empty-result behaviour."""

    def test_returns_results_from_repository(self):
        chunk = _make_chunk(chunk_text="cystic acne treatment")
        expected = _make_result(chunk, score=0.92)
        repo = FakeChunkRepository(search_results=[expected])
        service = SearchService(chunk_repository=repo, embedder=MockEmbedder())

        results = service.search(query="acne", top_k=5)

        assert len(results) == 1
        assert results[0].chunk.chunk_text == "cystic acne treatment"
        assert results[0].similarity_score == 0.92
        assert results[0].file_name == "test.pdf"

    def test_empty_results_returns_empty_list(self):
        """Zero matches must return [] without raising."""
        repo = FakeChunkRepository(search_results=[])
        service = SearchService(chunk_repository=repo, embedder=MockEmbedder())

        results = service.search(query="xyzxyz_no_match", top_k=5)

        assert results == []

    def test_user_id_forwarded_to_repository(self):
        repo = FakeChunkRepository()
        service = SearchService(chunk_repository=repo, embedder=MockEmbedder())

        service.search(query="foo", top_k=3, user_id="user-abc")

        assert repo.last_user_id == "user-abc"

    def test_top_k_forwarded_to_repository(self):
        repo = FakeChunkRepository()
        service = SearchService(chunk_repository=repo, embedder=MockEmbedder())

        service.search(query="foo", top_k=7)

        assert repo.last_top_k == 7


class TestSearchServiceErrorHandling:
    """Unexpected repository errors must be wrapped in SearchFailedError."""

    def test_repository_error_raises_search_failed_error(self):
        service = SearchService(
            chunk_repository=FailingChunkRepository(),
            embedder=MockEmbedder(),
        )

        with pytest.raises(SearchFailedError) as exc_info:
            service.search(query="problematic query", top_k=5)

        err = exc_info.value
        assert err.query == "problematic query"
        assert isinstance(err.original_error, RuntimeError)
        assert "Simulated pgvector failure" in str(err.original_error)

    def test_search_failed_error_message_contains_query(self):
        service = SearchService(
            chunk_repository=FailingChunkRepository(),
            embedder=MockEmbedder(),
        )

        with pytest.raises(SearchFailedError) as exc_info:
            service.search(query="my search query", top_k=5)

        assert "my search query" in str(exc_info.value)
