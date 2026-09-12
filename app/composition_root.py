import os
from functools import lru_cache
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from dotenv import load_dotenv
load_dotenv()

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama

from app.infrastructure.ocr.docling_engine import DoclingEngine
from app.infrastructure.database.document_repository import DocumentRepository
from app.infrastructure.database.extraction_result_repository import ExtractionResultRepository
from app.infrastructure.database.document_chunk_repository import DocumentChunkRepository
from app.infrastructure.storage.minio_storage import MinIOStorage
from app.infrastructure.langchain.e5_embeddings import E5EmbeddingsWrapper
from app.infrastructure.langchain.markdown_splitter import LangChainMarkdownSplitter
from app.services.document_service import DocumentService
from app.services.vectorization_service import VectorizationService
from app.services.search_service import SearchService
from app.services.rag_service import RAGService


@lru_cache(maxsize=1)
def get_file_storage() -> MinIOStorage:
    return MinIOStorage(
        endpoint_url=os.getenv("MINIO_ENDPOINT"),
        access_key=os.getenv("MINIO_ACCESS_KEY"),
        secret_key=os.getenv("MINIO_SECRET_KEY"),
        bucket_name=os.getenv("MINIO_BUCKET_NAME"),
    )


@lru_cache(maxsize=1)
def get_e5_embeddings_wrapper() -> E5EmbeddingsWrapper:
    model = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
    return E5EmbeddingsWrapper(model=model)


@lru_cache(maxsize=1)
def get_ollama_llm() -> ChatOllama:
    """Return singleton instance of ChatOllama for Gemma 3."""
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "gemma3:1b")
    return ChatOllama(
        model=model,
        base_url=base_url,
        temperature=0.1,
        repeat_penalty=1.2,
        top_p=0.9,
    )


@lru_cache(maxsize=1)
def get_ocr_engine() -> DoclingEngine:
    """Return singleton instance of DoclingEngine to prevent reloading models per-request."""
    return DoclingEngine()


def fail_stuck_documents(session: Session, error_message: str) -> int:
    """Composition helper to recover stuck PROCESSING/INDEXING documents on startup."""
    repo = DocumentRepository(session)
    return repo.fail_all_stuck_processing(error_message)


def build_document_service(session: Session) -> DocumentService:
    ocr_engine = get_ocr_engine()
    document_repository = DocumentRepository(session)
    extraction_result_repository = ExtractionResultRepository(session)
    chunk_repository = DocumentChunkRepository(session)

    return DocumentService(
        ocr_engine=ocr_engine,
        document_repository=document_repository,
        extraction_result_repository=extraction_result_repository,
        file_storage=get_file_storage(),
        chunk_repository=chunk_repository,
    )


def build_vectorization_service(session: Session) -> VectorizationService:
    return VectorizationService(
        document_repository=DocumentRepository(session),
        extraction_result_repository=ExtractionResultRepository(session),
        chunk_repository=DocumentChunkRepository(session),
        text_splitter=LangChainMarkdownSplitter(embedder=get_e5_embeddings_wrapper()),
    )


def build_search_service(session: Session) -> SearchService:
    """Build a SearchService wired to the shared E5 embedder singleton.

    Not cached: each request gets a fresh SearchService with its own
    session-bound DocumentChunkRepository — the same pattern used by
    build_document_service and build_vectorization_service.
    """
    return SearchService(
        chunk_repository=DocumentChunkRepository(session),
        embedder=get_e5_embeddings_wrapper(),
    )


def build_rag_service(session: Session) -> RAGService:
    """Build a RAGService wired to SearchService and ChatOllama via LangGraph."""
    return RAGService(
        search_service=build_search_service(session),
        llm_client=get_ollama_llm(),
    )


