"""SQLAlchemy ORM model for the ``audit_events`` table.

Phase 1A Slice 3. Mirrors migration ``c3e8a1f5d047`` column-for-column.
No ``relationship()`` fields, matching every other model in this codebase
-- and here that convention is also a control: an ORM relationship from
``audit_events`` to ``users`` would invite a lazy load that silently
joins actor PII into an audit read.

``actor_user_id`` carries no ``ForeignKey``. That is deliberate and is
explained in the migration docstring (plan section 8.4): a cascading FK
would delete audit history when a user row is removed, and a restricting
one would make user rows undeletable. Neither is acceptable, so the
column is a bare UUID resolved best-effort at read time.

``occurred_at`` is ``DateTime(timezone=True)``, deliberately unlike the
naive ``TIMESTAMP`` columns elsewhere in this schema. It is written by
the database's ``now()`` default rather than by the application, so the
recorded time cannot be skewed by an application clock or by a caller.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.db.base import Base


class AuditEventModel(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("recorded_seq", name="uq_audit_events_recorded_seq"),
        CheckConstraint(
            "actor_type IN ('USER', 'SYSTEM', 'ANONYMOUS')",
            name="ck_audit_events_actor_type",
        ),
        CheckConstraint(
            "result IN ('SUCCESS', 'DENIED', 'FAILED')",
            name="ck_audit_events_result",
        ),
        CheckConstraint(
            "actor_type <> 'USER' OR actor_user_id IS NOT NULL",
            name="ck_audit_events_user_actor_has_id",
        ),
        Index(
            "ix_audit_events_organization_occurred_at",
            "organization_id",
            text("occurred_at DESC"),
        ),
        Index("ix_audit_events_object", "object_type", "object_id"),
        Index("ix_audit_events_correlation_id", "correlation_id"),
        Index("ix_audit_events_action_occurred_at", "action", text("occurred_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    recorded_seq: Mapped[int] = mapped_column(
        BigInteger, Identity(always=False), nullable=False
    )
    event_schema_version: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("1")
    )
    # Nullable only for pre-tenant failures; see the migration docstring.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    object_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    object_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    previous_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    request_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    request_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)
