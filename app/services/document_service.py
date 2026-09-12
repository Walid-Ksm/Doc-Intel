from app.domain.interfaces.ocr_engine import OCREngineInterface
from app.domain.interfaces.document_repository import DocumentRepositoryInterface
from app.domain.interfaces.extraction_result_repository import (
    ExtractionResultRepositoryInterface,
)
from app.domain.interfaces.document_chunk_repository import (
    DocumentChunkRepositoryInterface,
)
from app.domain.interfaces.file_storage import FileStorageInterface
from app.domain.models.document import Document
from app.domain.models.extraction_result import ExtractionResult
from app.domain.exceptions import (
    DocumentNotFoundError,
    StorageError,
    ExtractionFailedError,
)

import tempfile
import os
import logging

logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(
        self,
        ocr_engine: OCREngineInterface,
        document_repository: DocumentRepositoryInterface,
        extraction_result_repository: ExtractionResultRepositoryInterface,
        file_storage: FileStorageInterface,
        chunk_repository: DocumentChunkRepositoryInterface,
    ):
        self._ocr_engine = ocr_engine
        self._document_repository = document_repository
        self._extraction_result_repository = extraction_result_repository
        self._file_storage = file_storage
        self._chunk_repository = chunk_repository


    def create_document(
        self,
        file_name: str,
        storage_path: str,
        user_id: str,
        document_id: str | None = None,
        version: int = 1,
    ) -> Document:
        document = Document(
            file_name=file_name,
            storage_path=storage_path,
            user_id=user_id,
            version=version,
            **({"id": document_id} if document_id else {}),
        )
        return self._document_repository.save(document)

    def create_documents_batch(self, params_list: list[dict]) -> list[Document]:
        documents = []
        for params in params_list:
            documents.append(
                Document(
                    file_name=params["file_name"],
                    storage_path=params["storage_path"],
                    user_id=params["user_id"],
                    version=params.get("version", 1),
                    **(
                        {"id": params["document_id"]}
                        if params.get("document_id")
                        else {}
                    ),
                )
            )
        return self._document_repository.save_all(documents)

    def process_document(self, document_id: str) -> None:
        document = self._document_repository.get_by_id(document_id)

        if document is None:
            raise DocumentNotFoundError(document_id)

        document.mark_processing()
        self._document_repository.save(document)

        try:
            try:
                file_bytes = self._file_storage.download(document.storage_path)
            except Exception as e:
                raise StorageError("download", document.storage_path, e) from e

            # Preserve the original extension so Docling can infer the file
            # type correctly.  Docling uses the extension (not content sniffing)
            # to decide how to parse the file, so a DOCX written with a .pdf
            # suffix would be silently misidentified.
            _, file_ext = os.path.splitext(document.file_name)
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=file_ext or ".pdf"
            ) as tmp_file:
                tmp_file.write(file_bytes)
                tmp_file_path = tmp_file.name


            try:
                extracted_text = self._ocr_engine.extract(tmp_file_path)
            except Exception as e:
                raise ExtractionFailedError(document.id, e) from e
            finally:
                os.remove(tmp_file_path)

            extraction_result = ExtractionResult(
                document_id=document.id,
                extracted_text=extracted_text,
                extraction_method="DOCLING",
            )
            self._extraction_result_repository.save(extraction_result)

            document.mark_extracted()
            self._document_repository.save(document)

        except (StorageError, ExtractionFailedError) as e:
            logger.exception("Processing failed for document %s: %s", document_id, e)
            try:
                document.mark_failed(error_message=str(e))
                self._document_repository.save(document)
            except Exception:
                logger.exception(
                    "CRITICAL: Could not mark document %s as FAILED. "
                    "It is now permanently stuck in PROCESSING.",
                    document_id,
                )

        except Exception as e:
            logger.exception(
                "Unexpected error while processing document %s: %s", document_id, e
            )
            try:
                document.mark_failed(error_message=f"Unexpected error: {e}")
                self._document_repository.save(document)
            except Exception:
                logger.exception(
                    "CRITICAL: Could not mark document %s as FAILED after unexpected error. "
                    "It is now permanently stuck in PROCESSING.",
                    document_id,
                )

    def get_document(self, document_id: str) -> "Document | None":
        """Return a Document by ID, or None if it does not exist."""
        return self._document_repository.get_by_id(document_id)

    def list_documents_for_user(self, user_id: str) -> "list[Document]":
        """Return all documents owned by the given user."""
        return self._document_repository.list_by_user(user_id)

    def get_latest_version(
        self, file_name: str, user_id: str
    ) -> "Document | None":
        """Return the most recent version of a named file for a user, or None."""
        return self._document_repository.get_latest_version_by_filename(
            file_name=file_name, user_id=user_id
        )

    def get_latest_extraction(self, document_id: str) -> "ExtractionResult | None":
        """Return the most recent extraction result for a document, or None."""
        return self._extraction_result_repository.get_latest_by_document_id(document_id)

    def delete_document(self, document_id: str) -> None:
        document = self._document_repository.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(document_id)

        # 1. MinIO cleanup: Fail-fast — if storage deletion fails, do NOT touch DB
        self._file_storage.delete(document.storage_path)

        # 2. DB cascade cleanup in explicit child-to-parent order
        try:
            self._extraction_result_repository.delete_by_document_id(document_id)
            self._chunk_repository.delete_by_document_id(document_id)
            self._document_repository.delete(document_id)
        except Exception as e:
            logger.exception("Failed to delete database records for document %s: %s", document_id, e)
            raise

