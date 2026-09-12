from abc import ABC, abstractmethod
from typing import Optional, List

from app.domain.models.document import Document


class DocumentRepositoryInterface(ABC):
    @abstractmethod
    def save(self, document: Document) -> Document:
        pass

    @abstractmethod
    def get_by_id(self, document_id: str) -> Optional[Document]:
        pass

    @abstractmethod
    def list_by_user(self, user_id: str) -> List[Document]:
        pass

    @abstractmethod
    def delete(self, document_id: str) -> None:
        pass

    @abstractmethod
    def get_latest_version_by_filename(
        self, file_name: str, user_id: str
    ) -> Optional[Document]:
        pass

    @abstractmethod
    def save_all(self, documents: List[Document]) -> List[Document]:
        pass

    @abstractmethod
    def fail_all_stuck_processing(self, error_message: str) -> int:
        """Reset documents stuck in PROCESSING or INDEXING to FAILED.

        Returns the number of documents that were updated.
        Called at server startup to recover from crash-interrupted pipelines.
        """
        pass
