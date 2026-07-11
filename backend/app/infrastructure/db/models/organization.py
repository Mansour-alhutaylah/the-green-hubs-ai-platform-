"""SQLAlchemy ORM model for the ``Organization`` table.

Reconciliation model: ``organizations`` already exists in the shared
Supabase database (created out-of-band, before this repo's Alembic
history began -- see the Sprint 3 schema-reconciliation migrations,
``12c7b2051fc6`` onward). This model is a column-for-column mirror of
that already-verified live schema, not a new design. No
``relationship()`` fields are declared -- nothing in the current
domain/repository layer needs to traverse from ``Organization`` to its
``users``/``engagements``.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), server_default=text("CURRENT_TIMESTAMP"), nullable=True
    )
