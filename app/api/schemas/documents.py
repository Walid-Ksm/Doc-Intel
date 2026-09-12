"""Pydantic response schemas for the document CRUD endpoints."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    document_id: str
    file_name: str
    status: str
    version: int
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime


class DocumentSummaryResponse(BaseModel):
    """Lightweight projection returned by GET /documents (list)."""
    document_id: str
    file_name: str
    status: str
    version: int
    error_message: Optional[str] = None
    created_at: datetime


class DocumentMetricsSummaryResponse(BaseModel):
    """Metrics aggregation response for dashboard."""
    total_documents: int
    indexed_count: int
    failed_count: int
    pending_count: int
    processing_count: int
    extracted_count: int
    indexing_count: int
    error_rate_percentage: float
    avg_processing_time_seconds: Optional[float] = None
    status_breakdown: dict[str, int]
