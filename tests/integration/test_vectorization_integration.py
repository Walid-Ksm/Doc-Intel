import pytest
import uuid
from typing import List

from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.document_repository import DocumentRepository
from app.infrastructure.database.extraction_result_repository import ExtractionResultRepository
from app.infrastructure.database.document_chunk_repository import DocumentChunkRepository
from app.services.vectorization_service import VectorizationService
from app.domain.exceptions import DocumentNotFoundError
from app.domain.models.document import Document, DocumentStatus
from app.domain.models.document_chunk import DocumentChunk
from app.domain.models.extraction_result import ExtractionResult
from app.domain.interfaces.text_splitter import TextSplitterInterface
from app.infrastructure.database.models import UserModel


# ---------------------------------------------------------------------------
# Fake text splitter — avoids loading the real HuggingFace model in tests.
# Returns deterministic chunks with valid 384-dim zero vectors so the DB
# write path (pgvector type check) is exercised without the model overhead.
# ---------------------------------------------------------------------------
class FakeTextSplitter(TextSplitterInterface):
    def split_and_embed(self, document_id: str, markdown_text: str) -> List[DocumentChunk]:
        chunk = DocumentChunk(
            document_id=document_id,
            chunk_text="Fake chunk from: " + markdown_text[:50],
            metadata={"Header 1": "Test"},
        )
        chunk.attach_embedding([0.0] * 384)
        return [chunk]


class FakeTextSplitterMultiChunk(TextSplitterInterface):
    """Returns exactly 3 chunks — used for the idempotency test."""
    def split_and_embed(self, document_id: str, markdown_text: str) -> List[DocumentChunk]:
        chunks = []
        for i in range(3):
            chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=i,
                chunk_text=f"Chunk {i}",
                metadata={},
            )
            chunk.attach_embedding([float(i)] * 384)
            chunks.append(chunk)
        return chunks


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _build_service(session, splitter: TextSplitterInterface) -> VectorizationService:
    return VectorizationService(
        document_repository=DocumentRepository(session),
        extraction_result_repository=ExtractionResultRepository(session),
        chunk_repository=DocumentChunkRepository(session),
        text_splitter=splitter,
    )


def _cleanup_document(session, doc_id: str) -> None:
    try:
        from app.infrastructure.database.models import (
            DocumentModel,
            DocumentChunkModel,
            ExtractionResultModel,
        )
        session.query(DocumentChunkModel).filter(
            DocumentChunkModel.document_id == doc_id
        ).delete(synchronize_session=False)
        session.query(ExtractionResultModel).filter(
            ExtractionResultModel.document_id == doc_id
        ).delete(synchronize_session=False)
        session.query(DocumentModel).filter(
            DocumentModel.id == doc_id
        ).delete(synchronize_session=False)
        session.commit()
    except Exception:
        session.rollback()


def _create_extracted_document(session) -> Document:
    """Insert a document in EXTRACTED state with an ExtractionResult row."""
    # Ensure the user exists to satisfy foreign key constraint
    user_id = "user-integration-test"
    existing_user = session.query(UserModel).filter_by(id=user_id).first()
    if not existing_user:
        user = UserModel(id=user_id, email="test@example.com", role="USER")
        session.add(user)
        session.commit()

    doc_repo = DocumentRepository(session)
    extraction_repo = ExtractionResultRepository(session)

    doc = Document(
        file_name=f"test_{uuid.uuid4()}.pdf",
        storage_path=f"documents/test_{uuid.uuid4()}.pdf",
        user_id=user_id,
    )
    doc.mark_processing()
    doc.mark_extracted()
    doc_repo.save(doc)

    result = ExtractionResult(
        document_id=doc.id,
        extracted_text="# Introduction\n\nThis is test content.",
        extraction_method="docling",
    )
    extraction_repo.save(result)

    return doc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_index_document_success(db_session):
    doc = _create_extracted_document(db_session)
    service = _build_service(db_session, FakeTextSplitter())

    try:
        service.index_document(doc.id)

        doc_repo = DocumentRepository(db_session)
        updated_doc = doc_repo.get_by_id(doc.id)
        assert updated_doc.status == DocumentStatus.INDEXED, (
            f"Expected INDEXED but got {updated_doc.status}"
        )

        chunk_repo = DocumentChunkRepository(db_session)
        chunks = chunk_repo.list_by_document(doc.id)
        assert len(chunks) == 1
        assert chunks[0].embedding is not None
        assert len(chunks[0].embedding) == 384
        assert chunks[0].chunk_index == 0
    finally:
        _cleanup_document(db_session, doc.id)


def test_index_document_idempotent(db_session):
    """Running index_document twice must not accumulate duplicate chunks."""
    doc = _create_extracted_document(db_session)
    service = _build_service(db_session, FakeTextSplitterMultiChunk())

    try:
        service.index_document(doc.id)

        # Manually reset to EXTRACTED to allow a second indexing run
        doc_repo = DocumentRepository(db_session)
        doc_again = doc_repo.get_by_id(doc.id)
        doc_again.mark_extracted()
        doc_repo.save(doc_again)

        service.index_document(doc.id)

        chunk_repo = DocumentChunkRepository(db_session)
        chunks = chunk_repo.list_by_document(doc.id)
        assert len(chunks) == 3, (
            f"Expected 3 chunks after second run but got {len(chunks)} — "
            "idempotency guard (delete_by_document_id) may not have fired."
        )
        assert [c.chunk_index for c in chunks] == [0, 1, 2]
    finally:
        _cleanup_document(db_session, doc.id)


def test_index_document_fails_if_no_extraction_result(db_session):
    """index_document must raise DocumentNotFoundError when no ExtractionResult exists."""
    user_id = "user-integration-test"
    existing_user = db_session.query(UserModel).filter_by(id=user_id).first()
    if not existing_user:
        user = UserModel(id=user_id, email="test@example.com", role="USER")
        db_session.add(user)
        db_session.commit()

    doc_repo = DocumentRepository(db_session)

    doc = Document(
        file_name=f"no_extraction_{uuid.uuid4()}.pdf",
        storage_path=f"documents/no_extraction_{uuid.uuid4()}.pdf",
        user_id=user_id,
    )
    doc.mark_processing()
    doc.mark_extracted()
    doc_repo.save(doc)
    # Intentionally do NOT create an ExtractionResult for this document

    service = _build_service(db_session, FakeTextSplitter())

    try:
        with pytest.raises(DocumentNotFoundError):
            service.index_document(doc.id)
    finally:
        _cleanup_document(db_session, doc.id)
