"""SQLAlchemy ORM model for the ``Document`` aggregate.

Structurally inspired by Hemaya's ``Policy`` model (``backend/models.py``):
PostgreSQL UUID primary keys and an indexed status/foreign-key column
pattern are reused, but written in SQLAlchemy 2.0 typed ``Mapped`` /
``mapped_column`` style against this project's async ``Base``. No
``relationship()`` fields are declared, since neither the ``Document``
domain entity nor ``IDocumentRepository`` (Sprint 1) reference related
aggregates yet.

MVP Slice 4 (Evidence Review Lifecycle) adds the five evidence-decision
columns. ``evidence_status`` declares the same initial state twice --
Python-side ``default`` here and ``server_default`` in the migration --
deliberately: the Python default makes an ORM-constructed row carry the
state before it is flushed (so fixtures see it without a refresh), while
the server default covers every path that does not go through this class
at all. Both spell the one value ``INITIAL_EVIDENCE_STATUS`` holds,
which is imported rather than repeated.

The other four columns have no default: they are written only by
``SQLAlchemyDocumentRepository.transition_evidence``'s conditional
UPDATE, and are meaningless -- and constraint-violating -- until a human
decision exists.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.domain.evidence.lifecycle import INITIAL_EVIDENCE_STATUS
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
    evidence_status: Mapped[str] = mapped_column(
        String, nullable=False, default=INITIAL_EVIDENCE_STATUS.value
    )
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    superseded_by_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="NO ACTION"),
        nullable=True,
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
