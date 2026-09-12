"""Integration tests for version-aware semantic search.

Verifies that when a user uploads multiple versions of the same file
(e.g. v1 and v2), semantic search only returns chunks belonging to the
latest INDEXED version (v2), and completely excludes obsolete v1 chunks.
"""

import pytest
import uuid
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.models import (
    UserModel,
    DocumentModel,
    DocumentChunkModel,
    DocumentStatusEnum,
)
from app.infrastructure.database.document_chunk_repository import DocumentChunkRepository


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def multi_version_docs(db_session):
    """Seed a user with v1 and v2 of 'contract.pdf' and ensure cleanup."""
    user_id = f"test-version-user-{uuid.uuid4().hex[:8]}"
    db_session.add(UserModel(id=user_id, email=f"{user_id}@test.com", role="USER"))
    db_session.commit()

    dummy_vector = [0.1] * 384

    # Document v1
    doc_v1 = DocumentModel(
        id=str(uuid.uuid4()),
        user_id=user_id,
        file_name="contract.pdf",
        storage_path=f"documents/contract_{uuid.uuid4()}/v1/contract.pdf",
        version=1,
        status=DocumentStatusEnum.INDEXED,
    )
    db_session.add(doc_v1)
    db_session.commit()

    chunk_v1 = DocumentChunkModel(
        id=str(uuid.uuid4()),
        document_id=doc_v1.id,
        chunk_text="Contract v1 old payment terms: 30 days net.",
        chunk_index=0,
        embedding=dummy_vector,
        metadata_json={"version": 1},
    )
    db_session.add(chunk_v1)
    db_session.commit()

    # Document v2
    doc_v2 = DocumentModel(
        id=str(uuid.uuid4()),
        user_id=user_id,
        file_name="contract.pdf",
        storage_path=f"documents/contract_{uuid.uuid4()}/v2/contract.pdf",
        version=2,
        status=DocumentStatusEnum.INDEXED,
    )
    db_session.add(doc_v2)
    db_session.commit()

    chunk_v2 = DocumentChunkModel(
        id=str(uuid.uuid4()),
        document_id=doc_v2.id,
        chunk_text="Contract v2 updated payment terms: 15 days net.",
        chunk_index=0,
        embedding=dummy_vector,
        metadata_json={"version": 2},
    )
    db_session.add(chunk_v2)
    db_session.commit()

    yield {
        "user_id": user_id,
        "doc_v1_id": doc_v1.id,
        "doc_v2_id": doc_v2.id,
        "chunk_v1_id": chunk_v1.id,
        "chunk_v2_id": chunk_v2.id,
        "dummy_vector": dummy_vector,
    }

    # Teardown: thoroughly clean up seeded records
    db_session.query(DocumentChunkModel).filter(
        DocumentChunkModel.document_id.in_([doc_v1.id, doc_v2.id])
    ).delete(synchronize_session=False)
    db_session.query(DocumentModel).filter(
        DocumentModel.id.in_([doc_v1.id, doc_v2.id])
    ).delete(synchronize_session=False)
    db_session.query(UserModel).filter(UserModel.id == user_id).delete(synchronize_session=False)
    db_session.commit()


def test_search_similar_only_returns_latest_version(db_session, multi_version_docs):
    repo = DocumentChunkRepository(db_session)
    results = repo.search_similar(
        query_embedding=multi_version_docs["dummy_vector"],
        top_k=10,
        user_id=multi_version_docs["user_id"],
    )

    result_chunk_ids = [r.chunk.id for r in results]
    result_doc_ids = [r.chunk.document_id for r in results]

    # Must contain v2 chunk
    assert multi_version_docs["chunk_v2_id"] in result_chunk_ids
    assert multi_version_docs["doc_v2_id"] in result_doc_ids

    # Must NOT contain v1 chunk
    assert multi_version_docs["chunk_v1_id"] not in result_chunk_ids
    assert multi_version_docs["doc_v1_id"] not in result_doc_ids
