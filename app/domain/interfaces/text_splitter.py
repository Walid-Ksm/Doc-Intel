from abc import ABC, abstractmethod
from typing import List

from app.domain.models.document_chunk import DocumentChunk


class TextSplitterInterface(ABC):
    @abstractmethod
    def split_and_embed(self, document_id: str, markdown_text: str) -> List[DocumentChunk]:
        pass
