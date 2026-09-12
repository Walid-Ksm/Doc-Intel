import pytest
import uuid
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.document_repository import DocumentRepository
from app.infrastructure.database.extraction_result_repository import (
    ExtractionResultRepository,
)
from app.composition_root import get_file_storage
from app.services.document_service import DocumentService
from app.domain.exceptions import DocumentNotFoundError
from app.domain.models.document import Document, DocumentStatus
from unittest.mock import Mock


from app.infrastructure.database.document_chunk_repository import (
    DocumentChunkRepository,
)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def document_service(db_session):

    # Use real repositories connected to PostgreSQL
    document_repo = DocumentRepository(db_session)
    extraction_repo = ExtractionResultRepository(db_session)
    chunk_repo = DocumentChunkRepository(db_session)

    # Use real MinIO storage (reads credentials from .env via composition root)
    file_storage = get_file_storage()

    # Mock the OCR Engine (Docling) to avoid heavy operations,
    # since we are only testing exception handling
    mock_ocr = Mock()

    return DocumentService(
        ocr_engine=mock_ocr,
        document_repository=document_repo,
        extraction_result_repository=extraction_repo,
        file_storage=file_storage,
        chunk_repository=chunk_repo,
    )



def test_integration_document_not_found(document_service):
    invalid_doc_id = str(uuid.uuid4())

    with pytest.raises(DocumentNotFoundError) as exc_info:
        document_service.process_document(invalid_doc_id)

    assert exc_info.value.document_id == invalid_doc_id


def test_integration_storage_error_handling(document_service, db_session):
    from app.infrastructure.database.models import UserModel
    user_id = "test-exceptions-user"
    if not db_session.query(UserModel).filter_by(id=user_id).first():
        db_session.add(UserModel(id=user_id, email=f"{user_id}@example.com", role="USER"))
        db_session.commit()

    document_repo = DocumentRepository(db_session)

    # 1. Arrange: Create a real document in the database, but point to a fake MinIO path
    fake_storage_path = f"documents/fake_file_{uuid.uuid4()}.pdf"
    doc = Document(
        file_name="fake.pdf", storage_path=fake_storage_path, user_id=user_id
    )
    saved_doc = document_repo.save(doc)

    try:
        document_service.process_document(saved_doc.id)

        updated_doc = document_repo.get_by_id(saved_doc.id)

        assert updated_doc.status == DocumentStatus.FAILED
        assert "Storage download failed" in updated_doc.error_message
        assert fake_storage_path in updated_doc.error_message
    finally:
        document_repo.delete(saved_doc.id)

