import pytest

from app.domain.interfaces.ocr_engine import OCREngineInterface
from app.domain.interfaces.document_repository import DocumentRepositoryInterface
from app.domain.interfaces.extraction_result_repository import (
    ExtractionResultRepositoryInterface,
)
from app.domain.models.document import Document, DocumentStatus
from app.domain.models.extraction_result import ExtractionResult
from app.services.document_service import DocumentService
from app.domain.interfaces.file_storage import FileStorageInterface


class FakeFileStorage(FileStorageInterface):
    def __init__(self):
        self._store = {}

    def upload(self, file_bytes: bytes, destination_path: str) -> str:
        self._store[destination_path] = file_bytes
        return destination_path

    def download(self, storage_path: str) -> bytes:
        return self._store.get(storage_path, b"")

    def delete(self, storage_path: str) -> None:
        self._store.pop(storage_path, None)


class FakeOCREngine(OCREngineInterface):
    def extract(self, file_path: str) -> str:
        return "## Fake extracted content"


class FakeDocumentRepository(DocumentRepositoryInterface):
    def __init__(self):
        self._store = {}

    def save(self, document):
        self._store[document.id] = document
        return document

    def get_by_id(self, document_id):
        return self._store.get(document_id)

    def list_by_user(self, user_id):
        return [d for d in self._store.values() if d.user_id == user_id]

    def delete(self, document_id):
        self._store.pop(document_id, None)

    def get_latest_version_by_filename(self, file_name, user_id):
        matches = [
            d
            for d in self._store.values()
            if d.file_name == file_name and d.user_id == user_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda d: d.version)

    def save_all(self, documents):
        for document in documents:
            self._store[document.id] = document
        return documents

    def fail_all_stuck_processing(self, error_message: str) -> int:
        # No-op in unit tests — in-memory documents never get stuck in
        # PROCESSING/INDEXING, so there's nothing to recover.
        return 0


from app.domain.interfaces.document_chunk_repository import (
    DocumentChunkRepositoryInterface,
)
from app.domain.exceptions import DocumentNotFoundError, StorageError


class FakeExtractionResultRepository(ExtractionResultRepositoryInterface):
    def __init__(self):
        self._store = []

    def save(self, extraction_result):
        self._store.append(extraction_result)
        return extraction_result

    def list_by_document(self, document_id):
        return [r for r in self._store if r.document_id == document_id]

    def get_latest_by_document_id(self, document_id):
        matches = [r for r in self._store if r.document_id == document_id]
        return matches[-1] if matches else None

    def delete_by_document_id(self, document_id: str) -> None:
        self._store = [r for r in self._store if r.document_id != document_id]


class FakeDocumentChunkRepository(DocumentChunkRepositoryInterface):
    def __init__(self):
        self._store = []

    def save_many(self, chunks):
        self._store.extend(chunks)
        return chunks

    def delete_by_document_id(self, document_id: str) -> None:
        self._store = [c for c in self._store if c.document_id != document_id]

    def list_by_document(self, document_id: str):
        return [c for c in self._store if c.document_id == document_id]

    def search_similar(self, query_embedding, top_k, user_id=None):
        # Not exercised by DocumentService tests — returns empty list.
        return []


def test_process_document_marks_extracted_on_success():
    document_repo = FakeDocumentRepository()
    extraction_repo = FakeExtractionResultRepository()
    file_storage = FakeFileStorage()
    chunk_repo = FakeDocumentChunkRepository()
    file_storage.upload(b"fake pdf bytes", "/tmp/test.pdf")

    service = DocumentService(
        ocr_engine=FakeOCREngine(),
        document_repository=document_repo,
        extraction_result_repository=extraction_repo,
        file_storage=file_storage,
        chunk_repository=chunk_repo,
    )

    document = service.create_document(
        file_name="test.pdf", storage_path="/tmp/test.pdf", user_id="user-123"
    )
    assert document.status == DocumentStatus.PENDING

    service.process_document(document.id)

    updated_document = document_repo.get_by_id(document.id)
    assert updated_document.status == DocumentStatus.EXTRACTED

    results = extraction_repo.list_by_document(document.id)
    assert len(results) == 1
    assert results[0].extracted_text == "## Fake extracted content"


class FailingOCREngine(OCREngineInterface):
    def extract(self, file_path: str) -> str:
        raise RuntimeError("Simulated Docling crash")


def test_process_document_marks_failed_on_extraction_error():
    document_repo = FakeDocumentRepository()
    extraction_repo = FakeExtractionResultRepository()
    file_storage = FakeFileStorage()
    chunk_repo = FakeDocumentChunkRepository()
    file_storage.upload(b"fake pdf bytes", "/tmp/test.pdf")

    service = DocumentService(
        ocr_engine=FailingOCREngine(),
        document_repository=document_repo,
        extraction_result_repository=extraction_repo,
        file_storage=file_storage,
        chunk_repository=chunk_repo,
    )

    document = service.create_document(
        file_name="test.pdf", storage_path="/tmp/test.pdf", user_id="user-123"
    )
    service.process_document(document.id)

    updated_document = document_repo.get_by_id(document.id)
    assert updated_document.status == DocumentStatus.FAILED
    assert "Simulated Docling crash" in updated_document.error_message

    results = extraction_repo.list_by_document(document.id)
    assert len(results) == 0


def test_delete_document_success_cascades():
    document_repo = FakeDocumentRepository()
    extraction_repo = FakeExtractionResultRepository()
    file_storage = FakeFileStorage()
    chunk_repo = FakeDocumentChunkRepository()

    service = DocumentService(
        ocr_engine=FakeOCREngine(),
        document_repository=document_repo,
        extraction_result_repository=extraction_repo,
        file_storage=file_storage,
        chunk_repository=chunk_repo,
    )

    file_storage.upload(b"data", "/tmp/test.pdf")
    doc = service.create_document(
        file_name="test.pdf", storage_path="/tmp/test.pdf", user_id="user-123"
    )
    extraction_repo.save(ExtractionResult(document_id=doc.id, extracted_text="txt", extraction_method="DOCLING"))

    service.delete_document(doc.id)

    assert document_repo.get_by_id(doc.id) is None
    assert len(extraction_repo.list_by_document(doc.id)) == 0
    assert len(chunk_repo.list_by_document(doc.id)) == 0
    assert file_storage.download("/tmp/test.pdf") == b""


class FailingFileStorage(FakeFileStorage):
    def delete(self, storage_path: str) -> None:
        raise StorageError("delete", storage_path, RuntimeError("MinIO unreachable"))


def test_delete_document_fails_fast_on_storage_error():
    document_repo = FakeDocumentRepository()
    extraction_repo = FakeExtractionResultRepository()
    file_storage = FailingFileStorage()
    chunk_repo = FakeDocumentChunkRepository()

    service = DocumentService(
        ocr_engine=FakeOCREngine(),
        document_repository=document_repo,
        extraction_result_repository=extraction_repo,
        file_storage=file_storage,
        chunk_repository=chunk_repo,
    )

    doc = service.create_document(
        file_name="test.pdf", storage_path="/tmp/test.pdf", user_id="user-123"
    )
    extraction_repo.save(ExtractionResult(document_id=doc.id, extracted_text="txt", extraction_method="DOCLING"))

    with pytest.raises(StorageError):
        service.delete_document(doc.id)

    # Assert nothing in DB was deleted
    assert document_repo.get_by_id(doc.id) is not None
    assert len(extraction_repo.list_by_document(doc.id)) == 1

