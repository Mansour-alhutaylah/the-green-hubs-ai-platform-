"""Pure domain entity for one recorded audit event.

Phase 1A Slice 3. Framework-independent: no SQLAlchemy, no FastAPI, no
Pydantic. Mirrors migration ``c3e8a1f5d047``.

**Frozen on purpose.** An audit event is a statement about something that
already happened, so there is no legitimate reason for any code to alter
one after construction. ``frozen=True`` makes "append-only" a property of
the type rather than a convention the next author has to know about --
this is layer 2 of the three-layer scheme in Phase 1A plan section 8.2.
Layers 1 and 2 are discipline; only layer 3 (database privilege) is a
real control, and it is **not yet in place** -- see the migration's
docstring. Nothing may describe these events as immutable or
tamper-evident.

``id`` and ``recorded_seq`` are ``None`` before persistence, following
the same convention as ``AnalysisRun`` and ``DocumentChunkEmbedding``.
``occurred_at`` is likewise ``None`` pre-persistence: the database's
``now()`` default is the authoritative clock, so the application does not
supply one and cannot skew it.

``organization_id`` is optional **only** to accommodate pre-tenant
failures -- a rejected token, or an identity with no provisioned profile
-- where no organization is known. Every business event must carry one;
that is enforced in ``AuditService``, not here, because the entity cannot
tell which kind of event it is being used for.

Nothing in this module validates payload contents. The data-minimisation
rules of plan section 8.5 (allow-listed state fields, forbidden-key
denylist) are enforced by ``app.services.audit.AuditService`` at the
moment of recording, so that a violation raises at the one place every
event passes through rather than in the many places events are built.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class ActorType(str, Enum):
    """Who acted. ``USER`` requires an ``actor_user_id`` (DB CHECK)."""

    USER = "USER"
    SYSTEM = "SYSTEM"
    ANONYMOUS = "ANONYMOUS"


class AuditResult(str, Enum):
    """How the attempt ended.

    ``DENIED`` is an authorization refusal -- the actor was identified and
    not permitted. ``FAILED`` is an error -- the operation was permitted
    and did not complete. Conflating them would make "who is probing this
    system" unanswerable.
    """

    SUCCESS = "SUCCESS"
    DENIED = "DENIED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """One recorded event. Immutable once constructed."""

    action: str
    actor_type: ActorType
    result: AuditResult
    correlation_id: str
    actor_user_id: UUID | None = None
    organization_id: UUID | None = None
    object_type: str | None = None
    object_id: UUID | None = None
    previous_state: dict | None = None
    new_state: dict | None = None
    reason: str | None = None
    request_method: str | None = None
    request_path: str | None = None
    client_ip: str | None = None
    user_agent: str | None = None
    event_schema_version: int = 1
    # Server-assigned. Present only on an event read back from storage.
    id: UUID | None = None
    recorded_seq: int | None = None
    occurred_at: datetime | None = None
