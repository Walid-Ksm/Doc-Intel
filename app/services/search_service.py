from typing import List, Optional

from app.domain.exceptions import DomainError, SearchFailedError
from app.domain.interfaces.document_chunk_repository import DocumentChunkRepositoryInterface
from app.domain.models.search_result import SearchResult
from app.infrastructure.langchain.e5_embeddings import E5EmbeddingsWrapper


class SearchService:
    """Orchestrates query embedding + vector similarity search.

    Intentionally thin: all pgvector query logic lives in the repository;
    all embedding logic lives in E5EmbeddingsWrapper.  This service only
    wires them together and provides error translation.

    NOTE: embed_query() is synchronous HuggingFace inference and will block
    the event loop on the request thread.  This is a known limitation shared
    with the rest of the application's sync infrastructure; resolving it
    (e.g. via run_in_executor) is deferred to a future infrastructure-wide
    async migration.
    """

    def __init__(
        self,
        chunk_repository: DocumentChunkRepositoryInterface,
        embedder: E5EmbeddingsWrapper,
    ) -> None:
        self._chunk_repository = chunk_repository
        self._embedder = embedder

    def search(
        self,
        query: str,
        top_k: int,
        user_id: Optional[str] = None,
    ) -> List[SearchResult]:
        """Embed query and return the top_k most similar document chunks.

        Args:
            query:   Raw natural-language search string.
            top_k:   Maximum number of results to return (1–20).
            user_id: If provided, restricts results to this user's documents.

        Returns:
            Ordered list of SearchResult, highest similarity first.
            Returns an empty list when no chunks match — never raises for
            empty results.

        Raises:
            SearchFailedError: Wraps any unexpected infrastructure exception.
        """
        try:
            # embed_query() internally prepends "query: " as required by E5.
            query_embedding = self._embedder.embed_query(query)
            return self._chunk_repository.search_similar(query_embedding, top_k, user_id)
        except DomainError:
            # Let domain errors (e.g. future access-control errors) propagate unchanged.
            raise
        except Exception as exc:
            raise SearchFailedError(query=query, original_error=exc) from exc
