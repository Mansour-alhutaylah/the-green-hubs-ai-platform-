"""The single point through which every audit event is recorded.

Phase 1A Slice 3. Implements plan sections 8.3 (two write modes) and 8.5
(data minimisation).

**Nothing writes to this service yet.** Wiring denial events is Slice 4
and success events Slice 5. This module exists so that when those slices
land, every event passes one enforcement point instead of each call site
re-deciding what is safe to record.

Two write modes, because a denied request has no transaction that
survives:

``record_in_transaction`` rides the caller's session and does not commit.
If the business operation rolls back, the event rolls back with it -- so
a ``SUCCESS`` event can never outlive the change it claims happened.

``record_out_of_band`` opens its own session and commits it. A denial or
a failure unwinds the request session without committing, so an event
staged there would vanish; this is the only way a refusal gets recorded
at all.

**Failure policy: fail-open with a mandatory error log.** An audit write
that fails must not turn an already-committed business operation into a
500. Plan section 8.3 records this as decision **D-3, still awaiting
management approval**, and notes the Phase 1 backlog prefers fail-closed
for admin-class actions -- of which there are none today. The behaviour
is therefore explicit, logged at ``ERROR`` with the correlation id, and
tested; it is not a silent skip. If D-3 is decided the other way, the
change is confined to ``_swallow`` below.

Data minimisation is enforced here, not trusted to callers:

* state payloads may only be built by :func:`state_snapshot`, which is a
  per-object-type **allow-list**;
* every payload additionally passes a **key denylist**, applied
  recursively to every key at every depth, and **raises** on a hit. A
  forbidden key is a programming error, so it fails loudly rather than
  being silently redacted -- silent redaction would let the mistake ship
  and hide the fact that a call site tried to log secrets.
"""

import logging
from typing import Any, Final, Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.audit_event import ActorType, AuditEvent
from app.domain.repositories.audit_event import IAuditEventRepository

logger = logging.getLogger("app.audit")

#: Substrings that must never appear in a state payload key. Checked as
#: substrings, not equality, so ``access_token`` and ``api_key_id`` are
#: caught as readily as ``token`` and ``key``.
FORBIDDEN_PAYLOAD_KEY_FRAGMENTS: Final[frozenset[str]] = frozenset(
    {
        "token",
        "key",
        "secret",
        "password",
        "authorization",
        "api_key",
        "content",
        "text",
        "embedding",
        "prompt",
        "snippet",
    }
)

#: The only fields that may be captured per object type (plan section 8.5).
#: Anything not listed here cannot reach the audit trail through
#: :func:`state_snapshot`, which is the only sanctioned way to build a
#: payload.
STATE_ALLOW_LIST: Final[Mapping[str, frozenset[str]]] = {
    "document": frozenset({"id", "engagement_id", "filename", "processing_status"}),
    "engagement": frozenset({"id", "organization_id", "title", "status"}),
    "organization": frozenset({"id", "name"}),
    "analysis_run": frozenset(
        {"id", "status", "analysis_type", "document_id", "engagement_id"}
    ),
}

#: Cap on ``reason`` so a long server-authored string cannot overflow the
#: ``varchar(500)`` column and fail the insert.
MAX_REASON_CHARS: Final = 500
#: Cap matching the ``user_agent varchar(256)`` column.
MAX_USER_AGENT_CHARS: Final = 256


class ForbiddenAuditPayloadError(RuntimeError):
    """Raised when a state payload carries a key the denylist forbids.

    Deliberately a programming error, not a client-visible failure: it
    means a call site tried to record something the audit trail must
    never hold.
    """


#: Depth cap for the recursive scan. JSONB audit payloads are shallow by
#: construction (``state_snapshot`` emits a flat mapping), so anything
#: deeper is either a mistake or an attempt to bury a key below the
#: scan. Exceeding the cap is refused rather than truncated -- a payload
#: this service cannot fully inspect is one it must not record.
MAX_PAYLOAD_DEPTH: Final = 6


def _reject_forbidden_keys(
    payload: Any,
    *,
    field: str,
    _depth: int = 0,
    _path: str = "",
) -> None:
    """Refuse any payload carrying a denylisted key **at any depth**.

    A top-level-only scan was a real bypass: ``{"metadata": {"token":
    ...}}`` and ``{"items": [{"password": ...}]}`` both passed it while
    carrying exactly what section 8.5 forbids. Nested containers are
    therefore walked, and the reported path names where the offending key
    was found so the fix is obvious from the error alone.

    Sanctioned payloads never reach the nested branches -- ``state_snapshot``
    emits a flat mapping of allow-listed scalars -- so this is a backstop
    against a hand-built payload, which is precisely the case a backstop
    exists for.
    """

    if payload is None:
        return

    if _depth > MAX_PAYLOAD_DEPTH:
        raise ForbiddenAuditPayloadError(
            f"Audit payload field '{field}' nests deeper than "
            f"{MAX_PAYLOAD_DEPTH} levels at '{_path}' and cannot be "
            "fully inspected; refusing to record it"
        )

    if isinstance(payload, Mapping):
        for raw_key, value in payload.items():
            lowered = str(raw_key).lower()
            for fragment in FORBIDDEN_PAYLOAD_KEY_FRAGMENTS:
                if fragment in lowered:
                    location = f"{_path}.{raw_key}" if _path else str(raw_key)
                    raise ForbiddenAuditPayloadError(
                        f"Audit payload field '{field}' contains forbidden key "
                        f"'{location}' (matched '{fragment}')"
                    )
            _reject_forbidden_keys(
                value,
                field=field,
                _depth=_depth + 1,
                _path=f"{_path}.{raw_key}" if _path else str(raw_key),
            )
        return

    # str/bytes are Sequences but carry no keys, so they are not walked.
    if isinstance(payload, (list, tuple)):
        for index, item in enumerate(payload):
            _reject_forbidden_keys(
                item,
                field=field,
                _depth=_depth + 1,
                _path=f"{_path}[{index}]",
            )


def state_snapshot(object_type: str, source: Mapping[str, Any]) -> dict[str, Any]:
    """Build an allow-listed state payload for ``object_type``.

    The **only** sanctioned way to produce ``previous_state`` /
    ``new_state``. Reads named keys from ``source`` and silently drops
    everything else, so passing an entity's full ``__dict__`` cannot leak
    an unlisted field. An unknown ``object_type`` raises rather than
    defaulting to "allow", keeping the catalog fail-closed.

    Absent keys are omitted rather than recorded as ``None``, so a
    snapshot never asserts that a field was empty when it was simply not
    supplied.
    """

    allowed = STATE_ALLOW_LIST.get(object_type)
    if allowed is None:
        raise ForbiddenAuditPayloadError(
            f"No audit state allow-list is defined for object type '{object_type}'"
        )
    snapshot: dict[str, Any] = {}
    for field in sorted(allowed):
        if field not in source:
            continue
        value = source[field]
        snapshot[field] = str(value) if isinstance(value, UUID) else value
    return snapshot


def _truncate(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value if len(value) <= limit else value[:limit]


class AuditService:
    """Records audit events. The one enforcement point for section 8.5."""

    def __init__(self, repository: IAuditEventRepository) -> None:
        self._repository = repository

    def _validate(self, event: AuditEvent) -> AuditEvent:
        """Apply the denylist and the column caps, or raise."""

        _reject_forbidden_keys(event.previous_state, field="previous_state")
        _reject_forbidden_keys(event.new_state, field="new_state")

        if event.actor_type is ActorType.USER and event.actor_user_id is None:
            # The database CHECK would catch this, but only at flush time,
            # by which point the failure is a driver error far from its
            # cause.
            raise ForbiddenAuditPayloadError(
                "A USER-attributed audit event requires an actor_user_id"
            )

        # Truncation rather than rejection: an over-long user agent is the
        # remote client's doing, not a programming error, and must not be
        # able to prevent an event from being recorded.
        return AuditEvent(
            action=event.action,
            actor_type=event.actor_type,
            result=event.result,
            correlation_id=event.correlation_id,
            actor_user_id=event.actor_user_id,
            organization_id=event.organization_id,
            object_type=event.object_type,
            object_id=event.object_id,
            previous_state=event.previous_state,
            new_state=event.new_state,
            reason=_truncate(event.reason, MAX_REASON_CHARS),
            request_method=event.request_method,
            request_path=event.request_path,
            client_ip=event.client_ip,
            user_agent=_truncate(event.user_agent, MAX_USER_AGENT_CHARS),
            event_schema_version=event.event_schema_version,
        )

    async def record_in_transaction(self, event: AuditEvent) -> None:
        """SUCCESS path. Stages the event on the repository's session.

        Does not commit: the event becomes durable exactly when the
        business transaction it rides does. A validation error is raised
        to the caller here rather than swallowed, because it is a
        programming error detected *before* anything was written.
        """

        await self._repository.append(self._validate(event))

    async def record_out_of_band(self, event: AuditEvent, session: AsyncSession) -> None:
        """DENIED / FAILED path. Commits ``session`` independently.

        ``session`` must be one the caller owns exclusively -- never the
        request session, which is unwinding without a commit. The
        dependency wiring in ``app.api.deps`` supplies a dedicated
        session for this; the parameter is explicit rather than
        constructed here so this service stays free of engine imports and
        remains unit-testable without a database.
        """

        validated = self._validate(event)
        try:
            await self._repository.append(validated)
            await session.commit()
        except Exception:
            await self._swallow(validated, session)

    async def _swallow(self, event: AuditEvent, session: AsyncSession) -> None:
        """Fail-open, loudly. See the module docstring on decision D-3."""

        logger.error(
            "AUDIT WRITE FAILED action=%s result=%s correlation_id=%s "
            "organization_id=%s -- the operation itself was unaffected",
            event.action,
            event.result.value,
            event.correlation_id,
            str(event.organization_id) if event.organization_id else "-",
            exc_info=True,
        )
        try:
            await session.rollback()
        except Exception:  # pragma: no cover - rollback of a dead session
            logger.error("Audit session rollback failed", exc_info=True)
