import pytest
import uuid
from unittest.mock import Mock, patch

from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.document_repository import DocumentRepository
from app.infrastructure.database.extraction_result_repository import ExtractionResultRepository
from app.infrastructure.database.document_chunk_repository import DocumentChunkRepository
from app.infrastructure.database.models import UserModel
from app.domain.models.document import Document, DocumentStatus
from app.domain.models.extraction_result import ExtractionResult
from app.domain.models.document_chunk import DocumentChunk
from app.infrastructure.celery.celery_app import celery_app
from app.infrastructure.celery.tasks import process_document_task
from app.domain.interfaces.text_splitter import TextSplitterInterface


class FakeTextSplitter(TextSplitterInterface):
    def split_and_embed(self, document_id: str, markdown_text: str) -> list[DocumentChunk]:
        chunk = DocumentChunk(
            document_id=document_id,
            chunk_text=f"Eager test chunk: {markdown_text[:30]}",
            chunk_index=0,
            metadata={"source": "celery_test"},
        )
        chunk.attach_embedding([0.1] * 384)
        return [chunk]


@pytest.fixture(autouse=True)
def configure_celery_eager():
    """Configure Celery to run tasks synchronously in eager mode for testing."""
    prev_eager = celery_app.conf.task_always_eager
    prev_propagate = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = prev_eager
    celery_app.conf.task_eager_propagates = prev_propagate


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user(db_session):
    user_id = "celery-test-user"
    user = db_session.query(UserModel).filter_by(id=user_id).first()
    if not user:
        user = UserModel(id=user_id, email="celery_test@example.com", role="USER")
        db_session.add(user)
        db_session.commit()
    return user


def test_process_document_task_eager_reaches_indexed(db_session, test_user):
    # 1. Arrange: Create a document in PENDING state
    doc_id = str(uuid.uuid4())
    doc_repo = DocumentRepository(db_session)
    doc = Document(
        id=doc_id,
        file_name="celery_test.pdf",
        storage_path=f"documents/celery_test_{doc_id}/v1/celery_test.pdf",
        user_id=test_user.id,
        status=DocumentStatus.PENDING,
    )
    doc_repo.save(doc)

    # 2. Mock storage, OCR engine, and vectorization text splitter to keep test fast & deterministic
    mock_file_storage = Mock()
    mock_file_storage.download.return_value = b"fake pdf content for celery test"

    mock_ocr_engine = Mock()
    mock_ocr_engine.extract.return_value = "# Celery Title\n\nDocument processed via Celery task queue."

    with patch("app.composition_root.get_file_storage", return_value=mock_file_storage), \
         patch("app.composition_root.DoclingEngine", return_value=mock_ocr_engine), \
         patch("app.composition_root.LangChainMarkdownSplitter", return_value=FakeTextSplitter()):

        # 3. Act: Dispatch the Celery task (runs synchronously in eager mode)
        async_result = process_document_task.delay(doc_id)

    # 4. Assert: Celery task completed successfully
    assert async_result.successful()

    # Re-fetch document from fresh query to verify DB status transition
    updated_doc = doc_repo.get_by_id(doc_id)
    assert updated_doc is not None
    assert updated_doc.status == DocumentStatus.INDEXED

    # Verify extraction result was saved
    extraction_repo = ExtractionResultRepository(db_session)
    extraction = extraction_repo.get_latest_by_document_id(doc_id)
    assert extraction is not None
    assert "Celery Title" in extraction.extracted_text

    # Verify chunks were vectorized and stored
    chunk_repo = DocumentChunkRepository(db_session)
    chunks = chunk_repo.list_by_document(doc_id)
    assert len(chunks) == 1
    assert chunks[0].embedding is not None

    # Cleanup
    doc_repo.delete(doc_id)
