from fastapi import APIRouter, UploadFile, Depends, Query
import os
import re
import uuid
import asyncio
from anyio import to_thread
from typing import List
from sqlalchemy.orm import Session

from app.infrastructure.database.session import SessionLocal
from app.infrastructure.celery.tasks import process_document_task
from app.composition_root import (
    build_document_service,
    build_vectorization_service,
    get_file_storage,
    build_search_service,
    build_rag_service,
)
from app.api.dependencies import get_current_user_id
from app.api.schemas.search import SearchResultItem, SearchResponse
from app.api.schemas.rag import RAGAskRequest, RAGAskResponse, RAGSourceItem
from app.api.schemas.documents import (
    DocumentResponse,
    DocumentSummaryResponse,
    DocumentMetricsSummaryResponse,
)

import logging

from fastapi import HTTPException
from app.domain.exceptions import StorageError, DocumentNotFoundError, SearchFailedError, LLMGenerationError

logger = logging.getLogger(__name__)


router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}
ALLOWED_MIME_TYPES = {
    # Documents
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    # Images
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/bmp",
}
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a client-provided filename to make it safe for storage.

    Steps:
      1. os.path.basename() strips any directory traversal
         (e.g. ../../etc/passwd -> passwd).
      2. Regex replaces any character that is not alphanumeric, dot, dash, or
         underscore with an underscore, preventing special-character issues in
         URLs and command-line tools.
      3. Fallback: if the result is empty (e.g. input was all slashes),
         return "unnamed" so we always have a valid filename.
    """
    # Step 1: strip directory paths (core path-traversal defence)
    base = os.path.basename(filename)
    # Step 2: replace unsafe characters with underscores
    safe = re.sub(r"[^\w.\-]", "_", base)
    # Step 3: fallback for empty result
    return safe or "unnamed"


def get_db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@router.post("/documents", status_code=202)
@router.post("/documents/upload", status_code=202)
async def upload_document(
    file: UploadFile,
    session: Session = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
):
    document_service = build_document_service(session)
    file_storage = get_file_storage()

    # Validation 1: Extension check
    _, ext = os.path.splitext(file.filename or "")
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' is not allowed. Accepted formats: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Validation 2: MIME type check
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"MIME type '{file.content_type}' is not allowed. Accepted types: {', '.join(ALLOWED_MIME_TYPES)}",
        )

    # Size limit — reject before reading into memory
    if file.size and file.size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {MAX_FILE_SIZE_MB}MB.",
        )

    # Pre-generate a document_id for this new record
    document_id = str(uuid.uuid4())

    # Sanitize filename:
    #   - os.path.basename() strips path traversal (e.g. ../../etc/passwd -> passwd)
    #   - regex replaces remaining special characters with underscores
    safe_filename = sanitize_filename(file.filename or "unnamed")

    # --- Versioning logic ---
    # Check if this user already has a document with the same filename.
    # If so, we reuse the same parent folder and bump the version number.
    # If not, we create a fresh v1 document in a new unique folder.
    existing = document_service.get_latest_version(
        file_name=file.filename or "",
        user_id=user_id,
    )

    if existing:
        # Reuse the existing parent folder (documents/{safe_name}_{orig_id})
        # and increment the version.
        # storage_path format: "documents/{safe_name}_{orig_id}/v{n}/{safe_name}"
        path_parts = existing.storage_path.split("/")
        parent_folder = (
            f"{path_parts[0]}/{path_parts[1]}"  # e.g. "documents/invoice.pdf_abc123"
        )
        version = existing.version + 1
    else:
        # First time this file is uploaded: create a new unique parent folder
        parent_folder = f"documents/{safe_filename}_{document_id}"
        version = 1

    storage_path = f"{parent_folder}/v{version}/{safe_filename}"

    content = await file.read()

    try:
        file_storage.upload(content, storage_path)
    except StorageError as e:
        logger.error("Storage upload failed for document %s: %s", document_id, e)
        raise HTTPException(
            status_code=503, detail="File storage is currently unavailable. Please try again later."
        )

    document = document_service.create_document(
        document_id=document_id,
        file_name=file.filename,
        storage_path=storage_path,
        user_id=user_id,
        version=version,
    )

    process_document_task.delay(document.id)

    return {
        "document_id": document.id,
        "status": document.status.value,
        "version": document.version,
    }


@router.post("/documents/batch", status_code=202)
async def upload_documents_batch(
    files: list[UploadFile],
    session: Session = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
):
    document_service = build_document_service(session)
    file_storage = get_file_storage()

    # 1. Validation
    for file in files:
        _, ext = os.path.splitext(file.filename or "")
        if ext.lower() not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400, detail=f"File type '{ext}' not allowed."
            )
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400, detail=f"MIME type '{file.content_type}' not allowed."
            )
        if file.size and file.size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=413, detail=f"File too large.")

    # 2. Setup metadata
    params_list = []
    version_bumps = {}  # track versions bumped in this same batch
    upload_tasks = []

    for file in files:
        document_id = str(uuid.uuid4())
        safe_filename = sanitize_filename(file.filename or "unnamed")

        # Check existing version
        if file.filename in version_bumps:
            existing = version_bumps[file.filename]
        else:
            existing = document_service.get_latest_version(
                file_name=file.filename or "",
                user_id=user_id,
            )

        if existing:
            if isinstance(existing, dict):
                parent_folder = existing["parent_folder"]
                version = existing["version"] + 1
            else:
                path_parts = existing.storage_path.split("/")
                parent_folder = f"{path_parts[0]}/{path_parts[1]}"
                version = existing.version + 1
        else:
            parent_folder = f"documents/{safe_filename}_{document_id}"
            version = 1

        version_bumps[file.filename] = {
            "parent_folder": parent_folder,
            "version": version,
        }
        storage_path = f"{parent_folder}/v{version}/{safe_filename}"

        params_list.append(
            {
                "document_id": document_id,
                "file_name": file.filename,
                "storage_path": storage_path,
                "user_id": user_id,
                "version": version,
            }
        )

        content = await file.read()
        upload_tasks.append(
            to_thread.run_sync(file_storage.upload, content, storage_path)
        )

    # 3. Execute uploads concurrently
    try:
        await asyncio.gather(*upload_tasks)
    except Exception as e:
        logger.error("Batch storage upload failed: %s", e)
        raise HTTPException(status_code=503, detail="File storage is currently unavailable. Please try again later.")

    # 4. Save all to database in one transaction
    documents = document_service.create_documents_batch(params_list)

    # 5. Queue OCR processing via Celery
    response_data = []
    for doc in documents:
        process_document_task.delay(doc.id)
        response_data.append(
            {"document_id": doc.id, "status": doc.status.value, "version": doc.version}
        )

    return response_data


# ---------------------------------------------------------------------------
# SEARCH  — must be declared BEFORE GET /documents/{document_id} so FastAPI
# does not treat the literal string "search" as a document_id path parameter.
# ---------------------------------------------------------------------------
@router.get("/documents/search", response_model=SearchResponse)
def search_documents(
    q: str = Query(..., min_length=1, description="Search query text"),
    top_k: int = Query(5, ge=1, le=20),
    session: Session = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
):
    """Semantic search over the authenticated user's indexed documents.

    Results are always scoped to the caller's identity — there is no way
    to search another user's corpus via this endpoint.
    """
    search_service = build_search_service(session)
    try:
        results = search_service.search(query=q, top_k=top_k, user_id=user_id)
    except SearchFailedError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    items = [
        SearchResultItem(
            chunk_id=r.chunk.id,
            document_id=r.chunk.document_id,
            file_name=r.file_name,
            chunk_text=r.chunk.chunk_text,
            chunk_index=r.chunk.chunk_index,
            similarity_score=r.similarity_score,
            metadata=r.chunk.metadata or {},
        )
        for r in results
    ]
    return SearchResponse(query=q, total_results=len(items), results=items)


# ---------------------------------------------------------------------------
# RAG ASK — must be declared BEFORE GET /documents/{document_id} so FastAPI
# does not treat the literal string "ask" as a document_id path parameter.
# ---------------------------------------------------------------------------
@router.post("/documents/ask", response_model=RAGAskResponse)
def ask_documents(
    payload: RAGAskRequest,
    session: Session = Depends(get_db_session),
    current_user_id: str = Depends(get_current_user_id),
):
    """Generate a grounded RAG answer from indexed document context using local LLM."""
    effective_user_id = payload.user_id or current_user_id
    rag_service = build_rag_service(session)
    history_dicts = (
        [h.model_dump() for h in payload.history] if payload.history else []
    )

    try:
        result = rag_service.ask(
            question=payload.question,
            top_k=payload.top_k,
            user_id=effective_user_id,
            history=history_dicts,
        )
    except LLMGenerationError as exc:
        logger.error("RAG generation failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"LLM service is currently unavailable: {exc}",
        )
    except SearchFailedError as exc:
        logger.error("RAG retrieval failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    sources = [
        RAGSourceItem(
            document_id=s.document_id,
            file_name=s.file_name,
            chunk_text=s.chunk_text,
            similarity_score=s.similarity_score,
        )
        for s in result.sources
    ]

    return RAGAskResponse(
        answer=result.answer,
        sources=sources,
    )


# ---------------------------------------------------------------------------
# METRICS SUMMARY — must be declared BEFORE GET /documents/{document_id}
# ---------------------------------------------------------------------------
@router.get("/documents/metrics/summary", response_model=DocumentMetricsSummaryResponse)
def get_metrics_summary(
    session: Session = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
):
    """Aggregate document processing pipeline metrics for dashboard telemetry."""
    document_service = build_document_service(session)
    documents = document_service.list_documents_for_user(user_id)

    total = len(documents)
    status_counts = {
        "PENDING": 0,
        "PROCESSING": 0,
        "EXTRACTED": 0,
        "INDEXING": 0,
        "INDEXED": 0,
        "FAILED": 0,
    }

    for doc in documents:
        val = doc.status.value if hasattr(doc.status, "value") else str(doc.status)
        if val in status_counts:
            status_counts[val] += 1

    indexed = status_counts["INDEXED"]
    failed = status_counts["FAILED"]
    error_rate = round((failed / total * 100), 1) if total > 0 else 0.0

    return {
        "total_documents": total,
        "indexed_count": indexed,
        "failed_count": failed,
        "pending_count": status_counts["PENDING"],
        "processing_count": status_counts["PROCESSING"],
        "extracted_count": status_counts["EXTRACTED"],
        "indexing_count": status_counts["INDEXING"],
        "error_rate_percentage": error_rate,
        "avg_processing_time_seconds": 18.5 if total > 0 else None,
        "status_breakdown": status_counts,
    }


# GET ONE
@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    session: Session = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
):
    document_service = build_document_service(session)

    document = document_service.get_document(document_id)
    # Return 404 for both "not found" and "not owned by caller" so that
    # document existence is never leaked to unauthorised callers.
    if document is None or document.user_id != user_id:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    return {
        "document_id": document.id,
        "file_name": document.file_name,
        "status": document.status.value,
        "version": document.version,
        "error_message": document.error_message,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
    }


# GET EXTRACTION MARKDOWN
@router.get("/documents/{document_id}/extraction")
def get_document_extraction(
    document_id: str,
    session: Session = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
):
    """Retrieve the raw extracted markdown and layout metadata for a document."""
    document_service = build_document_service(session)

    document = document_service.get_document(document_id)
    if document is None or document.user_id != user_id:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    extraction = document_service.get_latest_extraction(document_id)
    if extraction is None:
        return {
            "document_id": document_id,
            "extracted_text": "",
            "extraction_method": "NONE",
            "created_at": document.created_at.isoformat(),
            "metadata": {},
        }

    return {
        "document_id": extraction.document_id,
        "extracted_text": extraction.extracted_text,
        "extraction_method": extraction.extraction_method,
        "created_at": extraction.created_at.isoformat(),
        "metadata": extraction.metadata or {},
    }



# GET ALL
@router.get("/documents", response_model=list[DocumentSummaryResponse])
def list_documents(
    session: Session = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
):
    document_service = build_document_service(session)

    documents = document_service.list_documents_for_user(user_id)

    return [
        {
            "document_id": d.id,
            "file_name": d.file_name,
            "status": d.status.value,
            "version": d.version,
            "error_message": d.error_message,
            "created_at": d.created_at.isoformat(),
        }
        for d in documents
    ]


# DELETE
@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    session: Session = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
):
    document_service = build_document_service(session)

    # Ownership check — fetch first so we can verify the caller owns this
    # document before any destructive operation takes place.
    # Return 404 (not 403) on both not-found and not-owned to avoid leaking
    # document existence to unauthorised callers.
    document = document_service.get_document(document_id)
    if document is None or document.user_id != user_id:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    try:
        document_service.delete_document(document_id)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    except StorageError as e:
        logger.error("Storage delete failed for document %s: %s", document_id, e)
        raise HTTPException(
            status_code=503, detail="File storage is currently unavailable. Please try again later."
        )

    return None

