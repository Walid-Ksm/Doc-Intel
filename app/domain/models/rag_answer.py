from dataclasses import dataclass, field
from typing import List


@dataclass
class RAGSource:
    """Domain model representing a retrieved context chunk used for RAG generation."""

    document_id: str
    file_name: str
    chunk_text: str
    similarity_score: float
    chunk_id: str = ""
    chunk_index: int = 0


@dataclass
class RAGAnswer:
    """Domain model representing the final generated answer and the source references."""

    answer: str
    sources: List[RAGSource] = field(default_factory=list)
