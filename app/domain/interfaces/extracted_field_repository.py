from abc import ABC, abstractmethod
from typing import List

from app.domain.models.extracted_field import ExtractedField


class ExtractedFieldRepositoryInterface(ABC):
    @abstractmethod
    def save_many(self, fields: List[ExtractedField]) -> List[ExtractedField]:
        pass

    @abstractmethod
    def list_by_document(self, document_id: str) -> List[ExtractedField]:
        pass
