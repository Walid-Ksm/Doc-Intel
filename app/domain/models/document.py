from enum import Enum
from dataclasses import dataclass, field
import uuid
from datetime import datetime, timezone
from typing import Optional


class DocumentStatus(Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    EXTRACTED = "EXTRACTED"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


@dataclass
class Document:
    file_name: str
    storage_path: str
    user_id: str

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: int = 1
    status: DocumentStatus = DocumentStatus.PENDING
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def mark_processing(self):
        self.status = DocumentStatus.PROCESSING
        self.updated_at = datetime.now(timezone.utc)

    def mark_extracted(self):
        self.status = DocumentStatus.EXTRACTED
        self.updated_at = datetime.now(timezone.utc)

    def mark_indexing(self):
        self.status = DocumentStatus.INDEXING
        self.updated_at = datetime.now(timezone.utc)

    def mark_indexed(self):
        self.status = DocumentStatus.INDEXED
        self.updated_at = datetime.now(timezone.utc)

    def mark_failed(self, error_message: str):
        self.status = DocumentStatus.FAILED
        self.error_message = error_message
        self.updated_at = datetime.now(timezone.utc)
