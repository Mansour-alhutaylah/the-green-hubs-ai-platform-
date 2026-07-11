"""SQLAlchemy ORM model for the ``Document`` aggregate.

Structurally inspired by Hemaya's ``Policy`` model (``backend/models.py``):
PostgreSQL UUID primary keys and an indexed status/foreign-key column
pattern are reused, but written in SQLAlchemy 2.0 typed ``Mapped`` /
``mapped_column`` style against this project's async ``Base``. No
``relationship()`` fields are declared, since neither the ``Document``
domain entity nor ``IDocumentRepository`` (Sprint 1) reference related
aggregates yet.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.db.base import Base


class DocumentModel(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String, nullable=False, default="PENDING"
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("engagements.id", ondelete="NO ACTION"),
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
