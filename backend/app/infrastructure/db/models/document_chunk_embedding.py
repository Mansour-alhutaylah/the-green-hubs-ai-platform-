"""SQLAlchemy ORM model for the ``DocumentChunkEmbedding`` aggregate.

Sprint 3.6A, Vector Retrieval Foundation. Mirrors migration
``3f3acc7fc556`` column-for-column, including the composite lineage
foreign keys, the fixed-dimension CHECK, and the combined status/column
consistency CHECK -- see that migration's module docstring for the full
design rationale. No ``relationship()`` fields, matching every other
model in this codebase.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.db.base import Base

EMBEDDING_DIMENSION = 1536


class DocumentChunkEmbeddingModel(Base):
    __tablename__ = "document_chunk_embeddings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["chunk_id", "document_id"],
            ["document_chunks.id", "document_chunks.document_id"],
            name="fk_document_chunk_embeddings_chunk_lineage",
            ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["document_id", "engagement_id"],
            ["documents.id", "documents.engagement_id"],
            name="fk_document_chunk_embeddings_document_lineage",
            ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["engagement_id", "organization_id"],
            ["engagements.id", "engagements.organization_id"],
            name="fk_document_chunk_embeddings_engagement_lineage",
            ondelete="NO ACTION",
        ),
        UniqueConstraint(
            "chunk_id",
            "provider",
            "model",
            "model_version",
            name="uq_document_chunk_embeddings_identity",
        ),
        CheckConstraint(
            f"embedding_dimension = {EMBEDDING_DIMENSION}",
            name="ck_document_chunk_embeddings_dimension",
        ),
        CheckConstraint("attempt_count >= 1", name="ck_document_chunk_embeddings_attempt_count"),
        CheckConstraint(
            "status IN ('PROCESSING', 'COMPLETED', 'FAILED')",
            name="ck_document_chunk_embeddings_status",
        ),
        CheckConstraint(
            "(status = 'PROCESSING' AND embedding IS NULL AND error_message IS NULL) OR "
            "(status = 'COMPLETED' AND embedding IS NOT NULL AND error_message IS NULL) OR "
            "(status = 'FAILED' AND embedding IS NULL)",
            name="ck_document_chunk_embeddings_status_consistency",
        ),
        CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_document_chunk_embeddings_content_hash_format",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    engagement_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=True
    )
    content_hash: Mapped[str] = mapped_column(String(length=64), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="PROCESSING")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
