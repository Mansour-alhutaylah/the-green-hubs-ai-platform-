"""SQLAlchemy ORM model for the ``ExtractedText`` table.

Reconciliation model -- see ``organization.py``'s module docstring for
the same rationale. Mirrors the already-verified live
``extracted_text`` schema column-for-column.

``UNIQUE(document_id)`` added by Sprint 3.5 migration ``81a7fdde2d19``,
encoding the "one extracted-text record per Document" contract at the
database level -- no other column/nullability change.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class ExtractedText(Base):
    __tablename__ = "extracted_text"
    __table_args__ = (UniqueConstraint("document_id", name="uq_extracted_text_document_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    extracted_content: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), server_default=text("CURRENT_TIMESTAMP"), nullable=True
    )
