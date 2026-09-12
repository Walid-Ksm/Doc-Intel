from abc import ABC, abstractmethod
from typing import List, Optional

from app.domain.models.extraction_result import ExtractionResult


class ExtractionResultRepositoryInterface(ABC):
    @abstractmethod
    def save(self, extraction_result: ExtractionResult) -> ExtractionResult:
        pass

    @abstractmethod
    def list_by_document(self, document_id: str) -> List[ExtractionResult]:
        pass

    @abstractmethod
    def get_latest_by_document_id(self, document_id: str) -> Optional[ExtractionResult]:
        """Return the most recently created ExtractionResult for a document, or None."""
        pass

    @abstractmethod
    def delete_by_document_id(self, document_id: str) -> None:
        pass

