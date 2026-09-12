from dataclasses import dataclass, field
import uuid


@dataclass
class ExtractedField:
    document_id: str
    field_name: str
    field_value: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
