import logging
from typing import List

from app.domain.exceptions import DocumentNotFoundError, IndexingFailedError
from app.domain.interfaces.document_chunk_repository import DocumentChunkRepositoryInterface
from app.domain.interfaces.document_repository import DocumentRepositoryInterface
from app.domain.interfaces.extraction_result_repository import ExtractionResultRepositoryInterface
from app.domain.interfaces.text_splitter import TextSplitterInterface
from app.domain.models.document import DocumentStatus

logger = logging.getLogger(__name__)


class VectorizationService:
    def __init__(
        self,
        document_repository: DocumentRepositoryInterface,
        extraction_result_repository: ExtractionResultRepositoryInterface,
        chunk_repository: DocumentChunkRepositoryInterface,
        text_splitter: TextSplitterInterface,
    ):
        self._document_repository = document_repository
        self._extraction_result_repository = extraction_result_repository
        self._chunk_repository = chunk_repository
        self._text_splitter = text_splitter

    def index_document(self, document_id: str) -> None:
        # Step 1: Fetch and validate the document.
        document = self._document_repository.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(document_id)

        # Guard: only index documents that have been successfully extracted.
        # If a document is PENDING, PROCESSING, FAILED etc. we skip silently —
        # the caller (background task) controls the pipeline order.
        if document.status != DocumentStatus.EXTRACTED:
            logger.warning(
                "index_document called for document %s with status %s (expected EXTRACTED). Skipping.",
                document_id,
                document.status.value,
            )
            return

        try:
            # Step 2: Mark INDEXING so the status is visible immediately.
            document.mark_indexing()
            self._document_repository.save(document)  # commits

            # Step 3: Idempotency guard — delete any stale chunks from a
            # previous (failed) indexing attempt before inserting new ones.
            self._chunk_repository.delete_by_document_id(document_id)  # commits

            # Step 4: Retrieve the extracted Markdown text.
            # Uses get_latest_by_document_id (DESC order) so if multiple
            # ExtractionResult rows exist, we always get the most recent one.
            extraction_result = self._extraction_result_repository.get_latest_by_document_id(
                document_id
            )
            if extraction_result is None:
                raise DocumentNotFoundError(document_id)

            # Step 5: Chunk and embed the Markdown text.
            # split_and_embed handles header-aware splitting + E5 prefix embedding.
            chunks = self._text_splitter.split_and_embed(
                document_id=document_id,
                markdown_text=extraction_result.extracted_text,
            )

            # Step 6: Persist all chunks with their embeddings.
            if chunks:
                self._chunk_repository.save_many(chunks)  # commits
                logger.info(
                    "Persisted %d chunks for document %s.", len(chunks), document_id
                )
            else:
                logger.warning(
                    "No chunks produced for document %s. Document will be marked INDEXED "
                    "but the vector index will be empty.",
                    document_id,
                )

            # Step 7: Mark INDEXED — pipeline complete.
            document.mark_indexed()
            self._document_repository.save(document)  # commits

        except IndexingFailedError:
            # Already wrapped downstream — let it propagate unchanged.
            raise

        except DocumentNotFoundError:
            # The ExtractionResult row is missing.  The document is already in
            # INDEXING state, so we must explicitly transition it to FAILED
            # before re-raising — otherwise it stays stuck in INDEXING forever
            # (the startup recovery only rescues PROCESSING/INDEXING at boot,
            # not mid-run).
            logger.error(
                "No ExtractionResult found for document %s during indexing. "
                "Marking as FAILED so it does not get stuck in INDEXING.",
                document_id,
            )
            try:
                document.mark_failed(
                    error_message=(
                        "Indexing failed: no extraction result found. "
                        "Please re-upload the document to retry."
                    )
                )
                self._document_repository.save(document)
            except Exception:
                logger.exception(
                    "CRITICAL: Could not mark document %s as FAILED after missing "
                    "ExtractionResult. Document is now stuck in INDEXING.",
                    document_id,
                )
            raise

        except Exception as e:
            # log first, always — so the failure is debuggable even if mark_failed
            # itself subsequently errors.
            logger.exception(
                "Indexing failed for document %s: %s", document_id, e
            )
            try:
                document.mark_failed(error_message=str(e))
                self._document_repository.save(document)  # commits
            except Exception:
                logger.exception(
                    "CRITICAL: Could not mark document %s as FAILED after indexing error. "
                    "Document is now stuck in INDEXING.",
                    document_id,
                )
            raise IndexingFailedError(document_id, e) from e

