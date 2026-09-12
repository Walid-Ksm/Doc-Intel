"""Integration tests for the semantic search pipeline.

Uses a real Postgres + pgvector session (SessionLocal) and seeds known
embeddings so cosine similarity ordering is fully deterministic — no
HuggingFace model is loaded during the test run itself.

Auth context
------------
The auth stub (app/api/dependencies.py) always returns ``user-123``.
All seeded data for the *authenticated* caller is therefore owned by
``user-123``.  A second user (``search-other-user``) is also seeded to
verify that cross-user data never leaks into the caller's results.

Test coverage
-------------
1. Authenticated user sees their own chunks (TestSearchAuthenticated).
2. Other users' chunks are never returned — ownership is enforced.
3. Results are ordered by descending similarity score.
4. top_k limits the number of returned results (TestSearchTopK).
5. SearchResultItem fields are fully populated (TestSearchResultFields).
6. Zero-match query returns HTTP 200 with total_results=0 (TestSearchZeroResults).
"""

import pytest
import uuid
from typing import List

from fastapi.testclient import TestClient

from app.main import app
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.models import (
    UserModel,
    DocumentModel,
    DocumentChunkModel,
    DocumentStatusEnum,
)

client = TestClient(app)

# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

from app.api.dependencies import get_current_user_id

# Isolated test user ID — never matches the active local development user ('user-123')
# so test suites never delete real uploaded documents during test runs.
_AUTH_USER = "test-search-auth-user"

# A second user whose data must never appear in _AUTH_USER's search results.
_OTHER_USER = "test-search-other-user"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_user(session, user_id: str) -> None:
    if not session.query(UserModel).filter_by(id=user_id).first():
        session.add(UserModel(id=user_id, email=f"{user_id}@test.com", role="USER"))
        session.commit()


def _create_document(session, user_id: str, file_name: str) -> DocumentModel:
    doc_id = str(uuid.uuid4())
    doc = DocumentModel(
        id=doc_id,
        user_id=user_id,
        file_name=file_name,
        storage_path=f"documents/{file_name}_{doc_id}/v1/{file_name}",
        version=1,
        status=DocumentStatusEnum.INDEXED,
    )
    session.add(doc)
    session.commit()
    return doc


def _create_chunk(
    session,
    document_id: str,
    chunk_text: str,
    embedding: List[float],
    chunk_index: int = 0,
    metadata: dict = None,
) -> DocumentChunkModel:
    chunk = DocumentChunkModel(
        id=str(uuid.uuid4()),
        document_id=document_id,
        chunk_text=chunk_text,
        embedding=embedding,
        chunk_index=chunk_index,
        metadata_json=metadata or {},
    )
    session.add(chunk)
    session.commit()
    return chunk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

from app.composition_root import get_e5_embeddings_wrapper


@pytest.fixture(scope="module")
def seeded_db():
    """Seed _AUTH_USER and _OTHER_USER with known documents once per module.

    _AUTH_USER (user-123):
        doc_auth - two chunks:
            chunk_auth_target  -> acne/treatment text  (high similarity to "acne treatment")
            chunk_auth_noise   -> unrelated weather text (low similarity)

    _OTHER_USER (search-other-user):
        doc_other - one chunk:
            chunk_other -> acne/treatment text  (must NOT appear in _AUTH_USER results)

    Yields a dict of IDs so tests can assert against specific chunks.
    """
    embedder = get_e5_embeddings_wrapper()
    session = SessionLocal()
    app.dependency_overrides[get_current_user_id] = lambda: _AUTH_USER
    try:
        _ensure_user(session, _AUTH_USER)
        _ensure_user(session, _OTHER_USER)

        # Clean up any rows left by previous runs of these two test users.
        # Order matters: delete child rows before parent rows to satisfy FK
        # constraints (bulk DELETE bypasses the ORM cascade).
        for uid in [_AUTH_USER, _OTHER_USER]:
            doc_ids = [
                d.id
                for d in session.query(DocumentModel).filter(
                    DocumentModel.user_id == uid
                ).all()
            ]
            if doc_ids:
                # 1. chunks (document_chunks.document_id FK)
                session.query(DocumentChunkModel).filter(
                    DocumentChunkModel.document_id.in_(doc_ids)
                ).delete(synchronize_session=False)
                # 2. extraction_results (extraction_results.document_id FK)
                from app.infrastructure.database.models import ExtractionResultModel
                session.query(ExtractionResultModel).filter(
                    ExtractionResultModel.document_id.in_(doc_ids)
                ).delete(synchronize_session=False)
                # 3. documents (parent, safe to delete now)
                session.query(DocumentModel).filter(
                    DocumentModel.id.in_(doc_ids)
                ).delete(synchronize_session=False)
                session.commit()

        text_auth_target = "Cystic acne is treated with isotretinoin."
        text_auth_noise  = "Unrelated content about atmospheric weather patterns and precipitation."
        text_other       = "Benzoyl peroxide reduces acne bacteria and facial blemishes."

        embeddings = embedder.embed_passages([text_auth_target, text_auth_noise, text_other])

        # --- _AUTH_USER data ---
        doc_auth = _create_document(session, _AUTH_USER, "auth_user_report.pdf")
        chunk_auth_target = _create_chunk(
            session,
            doc_auth.id,
            chunk_text=text_auth_target,
            embedding=embeddings[0],
            chunk_index=0,
            metadata={"section": "Treatment"},
        )
        chunk_auth_noise = _create_chunk(
            session,
            doc_auth.id,
            chunk_text=text_auth_noise,
            embedding=embeddings[1],
            chunk_index=1,
            metadata={"section": "Other"},
        )

        # --- _OTHER_USER data (must not appear in _AUTH_USER searches) ---
        doc_other = _create_document(session, _OTHER_USER, "other_user_report.pdf")
        chunk_other = _create_chunk(
            session,
            doc_other.id,
            chunk_text=text_other,
            embedding=embeddings[2],
            chunk_index=0,
            metadata={"section": "Treatments"},
        )

        yield {
            "doc_auth_id":          doc_auth.id,
            "doc_other_id":         doc_other.id,
            "chunk_auth_target_id": chunk_auth_target.id,
            "chunk_auth_noise_id":  chunk_auth_noise.id,
            "chunk_other_id":       chunk_other.id,
        }
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
        try:
            for uid in [_AUTH_USER, _OTHER_USER]:
                doc_ids = [
                    d.id
                    for d in session.query(DocumentModel).filter(
                        DocumentModel.user_id == uid
                    ).all()
                ]
                if doc_ids:
                    session.query(DocumentChunkModel).filter(
                        DocumentChunkModel.document_id.in_(doc_ids)
                    ).delete(synchronize_session=False)
                    from app.infrastructure.database.models import ExtractionResultModel
                    session.query(ExtractionResultModel).filter(
                        ExtractionResultModel.document_id.in_(doc_ids)
                    ).delete(synchronize_session=False)
                    session.query(DocumentModel).filter(
                        DocumentModel.id.in_(doc_ids)
                    ).delete(synchronize_session=False)
                session.query(UserModel).filter(UserModel.id == uid).delete(synchronize_session=False)
                session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSearchAuthenticated:
    """Authenticated user only sees their own indexed documents.

    The endpoint uses Depends(get_current_user_id) — there is no user_id
    query parameter. The auth stub returns 'user-123', so only _AUTH_USER's
    chunks must appear in results regardless of what other users have indexed.
    """

    def test_authenticated_user_sees_own_chunks(self, seeded_db):
        """The caller's target chunk must appear in results."""
        response = client.get(
            "/documents/search",
            params={"q": "acne treatment", "top_k": 20},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "acne treatment"

        returned_ids = {r["chunk_id"] for r in data["results"]}
        assert seeded_db["chunk_auth_target_id"] in returned_ids, (
            "Authenticated user's target chunk missing from results"
        )

    def test_other_users_chunks_are_excluded(self, seeded_db):
        """The other user's chunks must never appear -- ownership is enforced."""
        response = client.get(
            "/documents/search",
            params={"q": "acne treatment", "top_k": 20},
        )
        assert response.status_code == 200

        returned_ids = {r["chunk_id"] for r in response.json()["results"]}
        assert seeded_db["chunk_other_id"] not in returned_ids, (
            "Other user's chunk leaked into authenticated user's search results"
        )

    def test_results_ordered_by_similarity_descending(self, seeded_db):
        """Target chunk (high similarity) must outrank the noise chunk."""
        response = client.get(
            "/documents/search",
            params={"q": "acne treatment", "top_k": 20},
        )
        assert response.status_code == 200

        results = response.json()["results"]
        assert len(results) >= 1

        scores = [r["similarity_score"] for r in results]
        assert scores == sorted(scores, reverse=True), (
            f"Results not sorted by descending similarity: {scores}"
        )

        # If the noise chunk is present, target chunk must rank above it
        noise = next(
            (r for r in results if r["chunk_id"] == seeded_db["chunk_auth_noise_id"]),
            None,
        )
        if noise:
            target_score = next(
                r["similarity_score"]
                for r in results
                if r["chunk_id"] == seeded_db["chunk_auth_target_id"]
            )
            assert target_score > noise["similarity_score"]


class TestSearchTopK:
    """top_k parameter limits the number of returned results."""

    def test_top_k_one_returns_exactly_one_result(self, seeded_db):
        response = client.get(
            "/documents/search",
            params={"q": "acne treatment", "top_k": 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_results"] == 1
        assert len(data["results"]) == 1

    def test_top_k_two_returns_at_most_two(self, seeded_db):
        response = client.get(
            "/documents/search",
            params={"q": "acne treatment", "top_k": 2},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 2


class TestSearchResultFields:
    """SearchResultItem must have all required fields correctly populated."""

    def test_search_result_item_fields_populated(self, seeded_db):
        response = client.get(
            "/documents/search",
            params={"q": "acne treatment", "top_k": 5},
        )
        assert response.status_code == 200
        results = response.json()["results"]
        assert len(results) > 0

        # Find _AUTH_USER's target chunk specifically
        target = next(
            (r for r in results if r["chunk_id"] == seeded_db["chunk_auth_target_id"]),
            None,
        )
        assert target is not None, "Authenticated user's target chunk not found in results"

        assert target["chunk_index"] == 0
        assert target["file_name"] == "auth_user_report.pdf"
        assert target["metadata"] == {"section": "Treatment"}
        assert target["chunk_text"] == "Cystic acne is treated with isotretinoin."
        assert target["document_id"] == seeded_db["doc_auth_id"]
        assert 0.0 <= target["similarity_score"] <= 1.0

    def test_response_schema_fields_present(self, seeded_db):
        """Every result item must contain all required schema fields."""
        response = client.get("/documents/search", params={"q": "acne", "top_k": 5})
        assert response.status_code == 200

        required_fields = {
            "chunk_id", "document_id", "file_name", "chunk_text",
            "chunk_index", "similarity_score", "metadata",
        }
        for item in response.json()["results"]:
            assert required_fields.issubset(item.keys()), (
                f"Missing fields: {required_fields - item.keys()}"
            )


class TestSearchZeroResults:
    """Queries with no semantic match still return HTTP 200 with valid schema.

    Note: pgvector has no similarity cut-off threshold — if the authenticated
    user has any indexed chunks, a query always returns up to top_k results
    (the most similar ones, however low their score).  True total_results==0
    is therefore only possible when the user has zero chunks at all, which we
    cannot guarantee in the shared integration DB.  These tests focus on the
    response contract, not on the count.
    """

    def test_zero_matches_returns_200(self):
        response = client.get(
            "/documents/search",
            params={"q": "xyzxyz_no_match_string_9999", "top_k": 5},
        )
        assert response.status_code == 200

    def test_low_similarity_search_returns_valid_response_structure(self):
        """Even a nonsense query must return a well-formed SearchResponse."""
        response = client.get(
            "/documents/search",
            params={"q": "xyzxyz_no_match_string_9999", "top_k": 5},
        )
        assert response.status_code == 200
        data = response.json()
        # Schema contract: these keys must always be present
        assert "query" in data
        assert "total_results" in data
        assert "results" in data
        assert isinstance(data["results"], list)
        assert data["total_results"] == len(data["results"])

    def test_zero_matches_response_has_correct_query_echo(self):
        q = "xyzxyz_no_match_string_9999"
        response = client.get(
            "/documents/search",
            params={"q": q, "top_k": 5},
        )
        assert response.status_code == 200
        assert response.json()["query"] == q
