"""SQLAlchemy ORM model for the ``AnalysisSourceReference`` aggregate.

Sprint 3.6B, RAG + Structured Sustainability Analysis Foundation.
Mirrors migration ``da0298a9c722`` column-for-column, including all four
composite tenant-lineage foreign keys -- see that migration's module
docstring for the full design rationale. No ``relationship()`` fields,
matching every other model in this codebase.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.db.base import Base


class AnalysisSourceReferenceModel(Base):
    __tablename__ = "analysis_source_references"
    __table_args__ = (
        ForeignKeyConstraint(
            ["analysis_run_id", "organization_id"],
            ["analysis_runs.id", "analysis_runs.organization_id"],
            name="fk_analysis_source_references_run_lineage",
            ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["chunk_id", "document_id"],
            ["document_chunks.id", "document_chunks.document_id"],
            name="fk_analysis_source_references_chunk_lineage",
            ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["document_id", "engagement_id"],
            ["documents.id", "documents.engagement_id"],
            name="fk_analysis_source_references_document_lineage",
            ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["engagement_id", "organization_id"],
            ["engagements.id", "engagements.organization_id"],
            name="fk_analysis_source_references_engagement_lineage",
            ondelete="NO ACTION",
        ),
        UniqueConstraint(
            "analysis_run_id", "chunk_id", name="uq_analysis_source_references_run_chunk"
        ),
        CheckConstraint("char_end > char_start", name="ck_analysis_source_references_char_range"),
        CheckConstraint(
            "citation_order >= 1", name="ck_analysis_source_references_citation_order"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    engagement_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    quoted_snippet: Mapped[str] = mapped_column(Text, nullable=False)
    citation_order: Mapped[int] = mapped_column(Integer, nullable=False)
    relevance_score: Mapped[float] = mapped_column(Numeric, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
