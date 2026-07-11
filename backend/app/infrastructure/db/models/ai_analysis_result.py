"""SQLAlchemy ORM model for the ``AIAnalysisResult`` table.

Reconciliation model -- see ``organization.py``'s module docstring for
the same rationale. Mirrors the already-verified live
``ai_analysis_results`` schema column-for-column.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class AIAnalysisResult(Base):
    __tablename__ = "ai_analysis_results"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    summary: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    recommendations: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), server_default=text("CURRENT_TIMESTAMP"), nullable=True
    )
