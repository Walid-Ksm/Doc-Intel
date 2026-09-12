"""Pydantic response schemas for the semantic search endpoint."""
from typing import List

from pydantic import BaseModel


class SearchResultItem(BaseModel):
    chunk_id: str
    document_id: str
    file_name: str
    chunk_text: str
    chunk_index: int
    similarity_score: float
    metadata: dict


class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[SearchResultItem]
