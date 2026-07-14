"""SQLAlchemy ORM model for the ``AnalysisRun`` aggregate.

Sprint 3.6B, RAG + Structured Sustainability Analysis Foundation.
Mirrors migration ``da0298a9c722`` column-for-column, including the
tenant-scoped idempotency UNIQUE constraint and the combined
status/column consistency CHECK -- see that migration's module
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
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.db.base import Base


class AnalysisRunModel(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="NO ACTION"),
        ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="NO ACTION"),
        ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="NO ACTION"),
        ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="NO ACTION"),
        UniqueConstraint(
            "organization_id", "request_hash", name="uq_analysis_runs_organization_request_hash"
        ),
        UniqueConstraint("id", "organization_id", name="uq_analysis_runs_id_organization_id"),
        CheckConstraint("attempt_count >= 1", name="ck_analysis_runs_attempt_count"),
        CheckConstraint(
            "status IN ('PROCESSING', 'COMPLETED', 'FAILED', 'INSUFFICIENT_EVIDENCE')",
            name="ck_analysis_runs_status",
        ),
        CheckConstraint(
            "(status = 'PROCESSING' AND structured_output IS NULL AND error_message IS NULL) OR "
            "(status = 'COMPLETED' AND structured_output IS NOT NULL AND error_message IS NULL) OR "
            "(status = 'FAILED' AND structured_output IS NULL) OR "
            "(status = 'INSUFFICIENT_EVIDENCE' AND structured_output IS NULL "
            "AND insufficient_evidence_reason IS NOT NULL)",
            name="ck_analysis_runs_status_consistency",
        ),
        CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'", name="ck_analysis_runs_request_hash_format"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    analysis_type: Mapped[str] = mapped_column(String, nullable=False)
    query_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    prompt_template_version: Mapped[str] = mapped_column(String, nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String, nullable=False)
    temperature: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    retrieval_top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_provider: Mapped[str] = mapped_column(String, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String, nullable=False)
    embedding_model_version: Mapped[str] = mapped_column(String, nullable=False)
    minimum_relevance_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(length=64), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="PROCESSING")
    structured_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    insufficient_evidence_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
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
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
