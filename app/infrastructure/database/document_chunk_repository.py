from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.interfaces.document_chunk_repository import (
    DocumentChunkRepositoryInterface,
)
from app.domain.models.document_chunk import DocumentChunk
from app.domain.models.search_result import SearchResult
from app.infrastructure.database.models import (
    DocumentChunkModel,
    DocumentModel,
    DocumentStatusEnum,
)


class DocumentChunkRepository(DocumentChunkRepositoryInterface):
    def __init__(self, session: Session):
        self._session = session

    def save_many(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        # Convert every domain chunk into its SQLAlchemy equivalent,
        # then add them ALL to the session before a single commit —
        # this batches every INSERT into one transaction, avoiding
        # the inefficiency of committing once per chunk.
        db_chunks = [
            DocumentChunkModel(
                id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                chunk_text=chunk.chunk_text,
                embedding=chunk.embedding,
                # Recall: metadata is a reserved name on SQLAlchemy's
                # Base, so the column is named metadata_json instead —
                # this is the exact translation point we discussed
                # when designing DocumentChunkModel.
                metadata_json=chunk.metadata,
            )
            for chunk in chunks
        ]

        self._session.add_all(db_chunks)
        self._session.commit()

        return chunks

    def delete_by_document_id(self, document_id: str) -> None:
        self._session.query(DocumentChunkModel).filter(
            DocumentChunkModel.document_id == document_id
        ).delete(synchronize_session=False)
        self._session.commit()


    def list_by_document(self, document_id: str) -> List[DocumentChunk]:
        db_chunks = (
            self._session.query(DocumentChunkModel)
            .filter(DocumentChunkModel.document_id == document_id)
            .order_by(DocumentChunkModel.chunk_index.asc())
            .all()
        )

        return [self._to_domain(c) for c in db_chunks]

    def _to_domain(self, db_chunk: DocumentChunkModel) -> DocumentChunk:
        return DocumentChunk(
            id=db_chunk.id,
            document_id=db_chunk.document_id,
            chunk_index=db_chunk.chunk_index,
            chunk_text=db_chunk.chunk_text,
            embedding=db_chunk.embedding,
            metadata=db_chunk.metadata_json,
        )

    def search_similar(
        self,
        query_embedding: List[float],
        top_k: int,
        user_id: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Return the top_k chunks most similar to query_embedding using pgvector
        cosine distance (<=>).  An inner join on DocumentModel fetches file_name
        in a single query.  If user_id is provided, results are scoped to that
        user's documents only.

        similarity_score = round(1.0 − cosine_distance, 4)
        A score of 1.0 means identical vectors; 0.0 means orthogonal.
        """
        distance_expr = DocumentChunkModel.embedding.cosine_distance(query_embedding)

        # Version filter: restrict candidates to the latest INDEXED version
        # of each file for the user so older superseded versions are never returned.
        latest_docs_subquery = (
            self._session.query(
                DocumentModel.file_name,
                DocumentModel.user_id,
                func.max(DocumentModel.version).label("max_version"),
            )
            .filter(DocumentModel.status == DocumentStatusEnum.INDEXED)
            .group_by(DocumentModel.file_name, DocumentModel.user_id)
        )
        if user_id is not None:
            latest_docs_subquery = latest_docs_subquery.filter(
                DocumentModel.user_id == user_id
            )
        latest_sub = latest_docs_subquery.subquery()

        query = (
            self._session.query(DocumentChunkModel, DocumentModel.file_name, distance_expr)
            .join(DocumentModel, DocumentChunkModel.document_id == DocumentModel.id)
            .join(
                latest_sub,
                (DocumentModel.file_name == latest_sub.c.file_name)
                & (DocumentModel.user_id == latest_sub.c.user_id)
                & (DocumentModel.version == latest_sub.c.max_version),
            )
            .filter(DocumentModel.status == DocumentStatusEnum.INDEXED)
        )

        if user_id is not None:
            query = query.filter(DocumentModel.user_id == user_id)

        query = query.order_by(distance_expr.asc()).limit(top_k)

        rows = query.all()

        results = []
        for db_chunk, file_name, cosine_dist in rows:
            similarity_score = round(1.0 - float(cosine_dist), 4)
            results.append(
                SearchResult(
                    chunk=self._to_domain(db_chunk),
                    similarity_score=similarity_score,
                    file_name=file_name,
                )
            )
        return results
