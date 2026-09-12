from abc import ABC, abstractmethod
from typing import List, Optional

from app.domain.models.document_chunk import DocumentChunk
from app.domain.models.search_result import SearchResult


class DocumentChunkRepositoryInterface(ABC):
    @abstractmethod
    def save_many(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        pass

    @abstractmethod
    def list_by_document(self, document_id: str) -> List[DocumentChunk]:
        pass

    @abstractmethod
    def delete_by_document_id(self, document_id: str) -> None:
        pass

    @abstractmethod
    def search_similar(
        self,
        query_embedding: List[float],
        top_k: int,
        user_id: Optional[str] = None,
    ) -> List[SearchResult]:
        pass
