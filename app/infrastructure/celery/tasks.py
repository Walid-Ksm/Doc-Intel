import logging
from app.infrastructure.celery.celery_app import celery_app
from app.infrastructure.database.session import SessionLocal
from app.composition_root import build_document_service, build_vectorization_service

logger = logging.getLogger(__name__)


@celery_app.task(name="process_document_task", rate_limit="10/m")
def process_document_task(document_id: str) -> None:
    """Celery background task to process and index a document.

    Executes:
      1. OCR extraction: PENDING -> PROCESSING -> EXTRACTED (or FAILED)
      2. Vector indexing: EXTRACTED -> INDEXING -> INDEXED (or FAILED)
    """
    logger.info("Celery task started for document_id=%s", document_id)
    session = SessionLocal()
    try:
        # Stage 1: OCR extraction
        document_service = build_document_service(session)
        document_service.process_document(document_id)

        # Stage 2: Vectorization
        # Status guard inside VectorizationService will skip if Stage 1 failed
        vectorization_service = build_vectorization_service(session)
        vectorization_service.index_document(document_id)

        logger.info("Celery task finished successfully for document_id=%s", document_id)
    except Exception as exc:
        logger.error("Celery task failed for document_id=%s: %s", document_id, exc, exc_info=True)
        raise
    finally:
        session.close()
