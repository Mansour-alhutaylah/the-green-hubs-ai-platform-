"""Append-only repository contract for audit events.

Phase 1A Slice 3, layer 1 of the three-layer append-only scheme in plan
section 8.2.

**This interface deliberately does not inherit ``IRepository``.** That
base declares ``update`` and ``delete`` (``app/domain/repositories/base.py``),
and inheriting it would hand every audit-event implementation a mutation
path that no caller should ever have. The unsafe shape is made
structurally unavailable rather than merely unused -- the same reasoning
that removed generic ``get``/``list`` from ``IRepository`` in MVP Slice 3.

The surface is exactly two methods: ``append`` and
``list_for_organization``. There is no ``get``, because a bare
``get(event_id)`` would read across tenants; a single event is reachable
only through the organization-scoped list.

``list_for_organization`` takes ``organization_id`` as a keyword-only
argument, matching every other tenant-scoped read in this codebase. That
naming is load-bearing: the tenant-scope guard
(``tests/domain/architecture/test_tenant_scope_guard.py``) parses call
sites in ``app/services`` and ``app/api`` and fails CI when a
tenant-scoped repository method is called without ``organization_id``.

Events whose ``organization_id`` is null -- pre-tenant failures such as a
rejected token -- are **not** returned by ``list_for_organization`` and
are deliberately unreachable through any tenant-scoped read. They belong
to no tenant, so exposing them inside one tenant's view would be a
cross-tenant leak in the opposite direction. Operator access to those
rows is an out-of-band concern, not an API concern.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.audit_event import AuditEvent


class IAuditEventRepository(ABC):
    """Append and organization-scoped read. No update, no delete."""

    @abstractmethod
    async def append(self, event: AuditEvent) -> None:
        """Stage ``event`` for insertion on the repository's session.

        Does **not** commit. Whether the event is durable is decided by
        whoever owns the transaction -- ``AuditService`` provides both a
        transaction-riding mode and an independently-committing mode, and
        that choice is the whole point of the two write paths (plan
        section 8.3).
        """

    @abstractmethod
    async def list_for_organization(
        self,
        *,
        organization_id: UUID,
        limit: int,
        offset: int,
    ) -> list[AuditEvent]:
        """Return one organization's events, most recent first.

        The tenant predicate lives in the SQL, not in a caller-side check.
        """

    @abstractmethod
    async def count_for_organization(self, *, organization_id: UUID) -> int:
        """Return the total number of events for one organization."""
