"""SQLAlchemy ORM model for the ``Engagement`` table.

Reconciliation model -- see ``organization.py``'s module docstring for
the same rationale. Mirrors the already-verified live ``engagements``
schema column-for-column. ``documents.engagement_id`` gains its foreign
key to this table separately, in Migration C (``73688728b480``).
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class Engagement(Base):
    __tablename__ = "engagements"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        # Indexed by migration ``a4f1c9d2e7b3`` (MVP Slice 3): this column
        # is the root of the tenant-ownership chain that every
        # document-side query joins through.
        PG_UUID(as_uuid=True), ForeignKey("organizations.id"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[Optional[str]] = mapped_column(
        String(50), server_default=text("'planning'::character varying"), nullable=True
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), server_default=text("CURRENT_TIMESTAMP"), nullable=True
    )
