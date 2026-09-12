from typing import List
from sqlalchemy.orm import Session

from app.domain.interfaces.extracted_field_repository import (
    ExtractedFieldRepositoryInterface,
)
from app.domain.models.extracted_field import ExtractedField
from app.infrastructure.database.models import ExtractedFieldModel


class ExtractedFieldRepository(ExtractedFieldRepositoryInterface):
    def __init__(self, session: Session):
        self._session = session

    def save_many(self, fields: List[ExtractedField]) -> List[ExtractedField]:
        db_fields = [
            ExtractedFieldModel(
                id=f.id,
                document_id=f.document_id,
                field_name=f.field_name,
                field_value=f.field_value,
            )
            for f in fields
        ]

        self._session.add_all(db_fields)
        self._session.commit()

        return fields

    def list_by_document(self, document_id: str) -> List[ExtractedField]:
        db_fields = (
            self._session.query(ExtractedFieldModel)
            .filter(ExtractedFieldModel.document_id == document_id)
            .all()
        )

        return [self._to_domain(f) for f in db_fields]

    def _to_domain(self, db_field: ExtractedFieldModel) -> ExtractedField:
        return ExtractedField(
            id=db_field.id,
            document_id=db_field.document_id,
            field_name=db_field.field_name,
            field_value=db_field.field_value,
        )
