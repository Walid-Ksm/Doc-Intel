from typing import List, Optional
from sqlalchemy.orm import Session

from app.domain.interfaces.extraction_result_repository import (
    ExtractionResultRepositoryInterface,
)

from app.domain.models.extraction_result import ExtractionResult

from app.infrastructure.database.models import ExtractionResultModel


class ExtractionResultRepository(ExtractionResultRepositoryInterface):
    def __init__(self, session: Session):
        self._session = session

    def save(self, extraction_result: ExtractionResult) -> ExtractionResult:
        db_result = ExtractionResultModel(
            id=extraction_result.id,
            document_id=extraction_result.document_id,
            extracted_text=extraction_result.extracted_text,
            extraction_method=extraction_result.extraction_method,
            created_at=extraction_result.created_at,
            metadata_json=extraction_result.metadata,
        )

        self._session.add(db_result)
        self._session.commit()

        return extraction_result

    def list_by_document(self, document_id: str) -> List[ExtractionResult]:
        db_results = (
            self._session.query(ExtractionResultModel)
            .filter(ExtractionResultModel.document_id == document_id)
            .order_by(ExtractionResultModel.created_at.asc())
            .all()
        )

        return [self._to_domain(r) for r in db_results]

    def _to_domain(self, db_result: ExtractionResultModel) -> ExtractionResult:
        return ExtractionResult(
            id=db_result.id,
            document_id=db_result.document_id,
            extracted_text=db_result.extracted_text,
            extraction_method=db_result.extraction_method,
            created_at=db_result.created_at,
            metadata=db_result.metadata_json,
        )

    def get_latest_by_document_id(self, document_id: str) -> Optional[ExtractionResult]:
        db_result = (
            self._session.query(ExtractionResultModel)
            .filter(ExtractionResultModel.document_id == document_id)
            .order_by(ExtractionResultModel.created_at.desc())
            .first()
        )
        if db_result is None:
            return None
        return self._to_domain(db_result)

    def delete_by_document_id(self, document_id: str) -> None:
        self._session.query(ExtractionResultModel).filter(
            ExtractionResultModel.document_id == document_id
        ).delete(synchronize_session=False)
        self._session.commit()

