from dataclasses import dataclass, field
import uuid
from typing import Optional, List

@dataclass
class DocumentChunk:
    document_id: str
    chunk_text: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # The embedding vector is populated after chunking, once the AI model runs.
    embedding: Optional[list[float]] = None

    # Sequential position of this chunk within the original document (0-indexed).
    chunk_index: int = 0

    # Per-chunk metadata (e.g. page number, section title).
    # Uses default_factory to ensure each instance gets its own dict.
    metadata: dict[str, str] = field(default_factory=dict)

    def attach_embedding(self, embedding: List[float]) -> None:
        self.embedding = embedding