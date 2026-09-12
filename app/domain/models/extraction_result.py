from dataclasses import dataclass, field
import uuid
from datetime import datetime, timezone


@dataclass
class ExtractionResult:
    document_id: str
    extracted_text: str
    extraction_method: str

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    metadata: dict = field(default_factory=dict)
