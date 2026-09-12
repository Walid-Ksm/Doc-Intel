import pytest
import uuid
from unittest.mock import Mock

from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.document_repository import DocumentRepository
from app.infrastructure.database.extraction_result_repository import (
    ExtractionResultRepository,
)
from app.infrastructure.database.document_chunk_repository import (
    DocumentChunkRepository,
)
from app.infrastructure.database.models import UserModel
from app.composition_root import get_file_storage
from app.services.document_service import DocumentService
from app.domain.models.document import Document
from app.domain.models.extraction_result import ExtractionResult
from app.domain.models.document_chunk import DocumentChunk
from app.domain.exceptions import StorageError


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def document_service(db_session):
    document_repo = DocumentRepository(db_session)
    extraction_repo = ExtractionResultRepository(db_session)
    chunk_repo = DocumentChunkRepository(db_session)
    file_storage = get_file_storage()
    mock_ocr = Mock()

    return DocumentService(
        ocr_engine=mock_ocr,
        document_repository=document_repo,
        extraction_result_repository=extraction_repo,
        file_storage=file_storage,
        chunk_repository=chunk_repo,
    )


def test_integration_cascading_delete(document_service, db_session):
    # 1. Arrange user
    user_id = "user-delete-integration-test"
    existing_user = db_session.query(UserModel).filter_by(id=user_id).first()
    if not existing_user:
        user = UserModel(id=user_id, email="delete_test@example.com", role="USER")
        db_session.add(user)
        db_session.commit()

    file_storage = get_file_storage()
    doc_repo = DocumentRepository(db_session)
    extraction_repo = ExtractionResultRepository(db_session)
    chunk_repo = DocumentChunkRepository(db_session)

    # 2. Upload real file to MinIO
    unique_id = str(uuid.uuid4())
    storage_path = f"documents/test_delete_{unique_id}.pdf"
    file_bytes = b"%PDF-1.4 test file content for cascade deletion"
    file_storage.upload(file_bytes, storage_path)

    # Assert file exists in MinIO
    downloaded = file_storage.download(storage_path)
    assert downloaded == file_bytes

    # 3. Create document in DB and advance to INDEXED
    doc = Document(
        id=unique_id,
        file_name="test_delete.pdf",
        storage_path=storage_path,
        user_id=user_id,
    )
    doc.mark_processing()
    doc.mark_extracted()
    doc.mark_indexed()
    doc_repo.save(doc)

    # 4. Create ExtractionResult row
    result = ExtractionResult(
        document_id=doc.id,
        extracted_text="# Section 1\nContent to be deleted.",
        extraction_method="DOCLING",
    )
    extraction_repo.save(result)

    # 5. Create DocumentChunk row
    chunk = DocumentChunk(
        document_id=doc.id,
        chunk_text="Chunk content to be deleted",
        metadata={"section": "1"},
    )
    chunk.attach_embedding([0.0] * 384)
    chunk_repo.save_many([chunk])

    # Sanity checks: Verify rows exist before deletion
    assert doc_repo.get_by_id(doc.id) is not None
    assert len(extraction_repo.list_by_document(doc.id)) == 1
    assert len(chunk_repo.list_by_document(doc.id)) == 1

    # 6. Act: Delete document
    document_service.delete_document(doc.id)

    # 7. Assert: Verify DB records and MinIO object are completely gone
    assert doc_repo.get_by_id(doc.id) is None
    assert len(extraction_repo.list_by_document(doc.id)) == 0
    assert len(chunk_repo.list_by_document(doc.id)) == 0

    with pytest.raises(StorageError):
        file_storage.download(storage_path)
