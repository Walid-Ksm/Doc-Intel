from sqlalchemy.orm import declarative_base

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from enum import Enum as PyEnum
from sqlalchemy import Enum as SQLEnum

from pgvector.sqlalchemy import Vector

from sqlalchemy.dialects.postgresql import JSONB

Base = declarative_base()

DOCUMENTS_ID_FK = "documents.id"
CASCADE_ALL_DELETE_ORPHAN = "all, delete-orphan"


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, nullable=False, unique=True, index=True)
    role = Column(String, nullable=False)


class DocumentStatusEnum(PyEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    EXTRACTED = "EXTRACTED"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class DocumentModel(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    user_id = Column(
        String,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    file_name = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    status = Column(
        SQLEnum(DocumentStatusEnum), nullable=False, default=DocumentStatusEnum.PENDING
    )
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ORM Relationships for cascading deletes
    extraction_results = relationship(
        "ExtractionResultModel", backref="document", cascade=CASCADE_ALL_DELETE_ORPHAN
    )
    extracted_fields = relationship(
        "ExtractedFieldModel", backref="document", cascade=CASCADE_ALL_DELETE_ORPHAN
    )
    document_chunks = relationship(
        "DocumentChunkModel", backref="document", cascade=CASCADE_ALL_DELETE_ORPHAN
    )


class ExtractionResultModel(Base):
    __tablename__ = "extraction_results"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey(DOCUMENTS_ID_FK), nullable=False)
    extracted_text = Column(Text, nullable=False)
    extraction_method = Column(String, nullable=False)
    metadata_json = Column(JSONB, nullable=True, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ExtractedFieldModel(Base):
    __tablename__ = "extracted_fields"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey(DOCUMENTS_ID_FK), nullable=False)
    field_name = Column(String, nullable=False)
    field_value = Column(Text, nullable=False)


class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey(DOCUMENTS_ID_FK), nullable=False)
    chunk_text = Column(Text, nullable=False)

    # Sequential position within the parent document (0-indexed)
    chunk_index = Column(Integer, nullable=False, default=0)

    # intfloat/multilingual-e5-small produces 384-dimensional vectors.
    # Matches the vector(384) column applied by scripts/migrate_embedding_dimension.py.
    embedding = Column(Vector(384), nullable=True)

    metadata_json = Column(JSONB, nullable=True, default=dict)

    # HNSW index for sub-millisecond approximate nearest-neighbour searches.
    # m=16         : number of bi-directional links per node (higher = better recall,
    #                more memory). 16 is the pgvector recommended default.
    # ef_construction=64 : size of the dynamic candidate list during build
    #                (higher = better index quality, slower build). 64 is a
    #                standard starting point for production workloads.
    # vector_cosine_ops : distance function — matches the cosine similarity
    #                used by the intfloat/multilingual-e5 model family.
    __table_args__ = (
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
