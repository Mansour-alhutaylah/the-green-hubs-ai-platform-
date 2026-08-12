"""Abstract repository interface for ``Engagement`` entities.

Extends the generic ``IRepository`` CRUD contract with an
``organization_id`` filter on ``list``/``count`` (needed for the list
endpoint's tenant scope) and ``count()`` (needed for pagination totals)
-- neither is expressible by the generic interface alone. ``delete()``
is inherited from ``IRepository`` and is implemented at the
infrastructure layer solely so integration tests can remove the exact
rows they create, mirroring ``IOrganizationRepository``.

This repository must never query ``organizations`` -- Organization
existence is checked in ``EngagementService`` via
``IOrganizationRepository``, not here.

Sprint 3.5.1 (Tenant Isolation & API Security) added
``get_for_organization``/``update_for_organization``/``count`` as
tenant-scoped methods alongside the inherited, unscoped
``get``/``list``. At the time ``list``'s ``organization_id`` had to stay
*optional*: it overrode ``IRepository[Engagement].list(*, limit, offset)``,
and narrowing an inherited signature breaks Liskov substitutability
(mypy confirmed it), so the guarantee rested on ``EngagementService``
never calling it unscoped.

MVP Slice 3 closure removed ``get`` and ``list`` from ``IRepository``
itself (see that module for why a generic contract cannot express tenant
scope). That dissolves the LSP constraint entirely, and both loose ends
are now closed properly:

- ``list()`` is bespoke to this interface, so ``organization_id`` is
  **mandatory** -- there is no longer a signature through which an
  unscoped, cross-tenant engagement listing can be requested at all;
- ``count()`` likewise takes a mandatory ``organization_id``;
- there is **no unscoped ``get``**. ``get_for_organization`` is the only
  read, so a cross-tenant Engagement id cannot be resolved to a row by
  any call this interface offers.

``update``/``delete`` remain inherited from ``IRepository``. They take an
Engagement the caller must already hold -- obtainable only through
``get_for_organization`` -- and ``EngagementService`` writes exclusively
through ``update_for_organization``; the plain ``update``/``delete`` exist
for contract completeness and integration-test cleanup.
"""

from abc import ABC, abstractmethod
from typing import Sequence
from uuid import UUID

from app.domain.entities.engagement import Engagement
from app.domain.repositories.base import IRepository


class IEngagementRepository(IRepository[Engagement], ABC):
    @abstractmethod
    async def list(
        self, *, organization_id: UUID, limit: int = 100, offset: int = 0
    ) -> Sequence[Engagement]:
        """Tenant-scoped, paginated listing. ``organization_id`` is
        mandatory: there is no signature here that yields a cross-tenant
        page."""
        ...

    @abstractmethod
    async def count(self, *, organization_id: UUID) -> int: ...

    @abstractmethod
    async def get_for_organization(
        self, entity_id: UUID, *, organization_id: UUID
    ) -> Engagement | None:
        """Tenant-scoped lookup: the SQL predicate requires both
        ``entity_id`` and ``organization_id`` to match in the same
        query, so a cross-tenant id and a genuinely nonexistent id are
        indistinguishable -- both return ``None``."""
        ...

    @abstractmethod
    async def update_for_organization(
        self, entity: Engagement, *, organization_id: UUID
    ) -> Engagement:
        """Tenant-scoped update: the target row's existing
        ``organization_id`` must match, enforced as part of the same
        lookup used to resolve the row to update -- not via a separate,
        earlier check that a write could race past. Raises
        ``NotFoundError`` if no matching row exists, including the
        cross-tenant case."""
        ...
