"""SQLAlchemy ORM model for the ``DocumentChunk`` aggregate.

Sprint 3.5, Document Processing Foundation. Mirrors ``DocumentModel``'s
style (typed ``Mapped``/``mapped_column``, no ``relationship()`` fields).
Unlike the reconciliation models, this table has no historical live data
-- see migration ``81a7fdde2d19`` for the full design rationale (NOT
NULL ``document_id``, timezone-aware ``created_at``).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.db.base import Base


class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "chunk_index", name="uq_document_chunks_document_id_chunk_index"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="NO ACTION"),
        index=True,
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
