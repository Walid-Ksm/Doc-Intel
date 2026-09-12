from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.domain.interfaces.document_repository import DocumentRepositoryInterface

from app.domain.models.document import Document, DocumentStatus

from app.infrastructure.database.models import DocumentModel, DocumentStatusEnum


class DocumentRepository(DocumentRepositoryInterface):
    def __init__(self, session: Session):
        self._session = session

    def save(self, document: Document) -> Document:
        db_document = DocumentModel(
            id=document.id,
            user_id=document.user_id,
            file_name=document.file_name,
            storage_path=document.storage_path,
            version=document.version,
            status=DocumentStatusEnum(document.status.value),
            error_message=document.error_message,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

        self._session.merge(db_document)
        self._session.commit()
        return document

    def save_all(self, documents: List[Document]) -> List[Document]:
        for document in documents:
            db_document = DocumentModel(
                id=document.id,
                user_id=document.user_id,
                file_name=document.file_name,
                storage_path=document.storage_path,
                version=document.version,
                status=DocumentStatusEnum(document.status.value),
                error_message=document.error_message,
                created_at=document.created_at,
                updated_at=document.updated_at,
            )
            self._session.merge(db_document)
        self._session.commit()
        return documents

    def get_by_id(self, document_id: str) -> Optional[Document]:
        db_document = (
            self._session.query(DocumentModel)
            .filter(DocumentModel.id == document_id)
            .first()
        )

        if db_document is None:
            return None

        return self._to_domain(db_document)

    def list_by_user(self, user_id: str) -> List[Document]:
        db_documents = (
            self._session.query(DocumentModel)
            .filter(DocumentModel.user_id == user_id)
            .all()
        )

        return [self._to_domain(d) for d in db_documents]

    def _to_domain(self, db_document: DocumentModel) -> Document:
        return Document(
            id=db_document.id,
            user_id=db_document.user_id,
            file_name=db_document.file_name,
            storage_path=db_document.storage_path,
            version=db_document.version,
            status=DocumentStatus(db_document.status.value),
            error_message=db_document.error_message,
            created_at=db_document.created_at,
            updated_at=db_document.updated_at,
        )

    def get_latest_version_by_filename(
        self, file_name: str, user_id: str
    ) -> Optional[Document]:
        db_document = (
            self._session.query(DocumentModel)
            .filter(
                DocumentModel.file_name == file_name,
                DocumentModel.user_id == user_id,
            )
            .order_by(DocumentModel.version.desc())
            .first()
        )
        if db_document is None:
            return None
        return self._to_domain(db_document)

    def delete(self, document_id: str) -> None:
        db_document = (
            self._session.query(DocumentModel)
            .filter(DocumentModel.id == document_id)
            .first()
        )
        if db_document is not None:
            self._session.delete(db_document)
            self._session.commit()

    def fail_all_stuck_processing(self, error_message: str) -> int:
        """Reset documents stuck in PROCESSING or INDEXING to FAILED.

        A server crash while a background task is running can leave documents
        in PROCESSING (OCR stage) or INDEXING (vectorization stage).  Both
        states represent in-flight work that died with the process and will
        never complete on their own.
        """
        updated_count = (
            self._session.query(DocumentModel)
            .filter(
                DocumentModel.status.in_([
                    DocumentStatusEnum.PROCESSING,
                    DocumentStatusEnum.INDEXING,
                ])
            )
            .update(
                {
                    DocumentModel.status: DocumentStatusEnum.FAILED,
                    DocumentModel.error_message: error_message,
                    DocumentModel.updated_at: datetime.now(timezone.utc),
                },
                synchronize_session=False,
            )
        )
        self._session.commit()
        return updated_count
