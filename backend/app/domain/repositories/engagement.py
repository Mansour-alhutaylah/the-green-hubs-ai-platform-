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

Sprint 3.5.1 (Tenant Isolation & API Security): two different inheritance
situations get two different fixes, both chosen as the smallest
architecture-compatible adjustment rather than a redesign of
``IRepository``:

- ``count()`` is bespoke to this interface (not part of
  ``IRepository[Engagement]``'s contract at all), so its
  ``organization_id`` filter is made outright mandatory here -- no LSP
  concern, since there is no inherited signature to stay compatible
  with.
- ``list()`` *is* inherited from ``IRepository[Engagement]`` with the
  signature ``list(*, limit=100, offset=0)`` -- no scope parameter at
  all. This override already widened it with an *optional*
  ``organization_id`` before this sprint; making it outright mandatory
  breaks Liskov substitutability (confirmed by mypy: a caller honoring
  the base ``IRepository[Engagement]`` contract could call
  ``list(limit=x, offset=y)`` and get an unscoped, cross-tenant result).
  So ``organization_id`` stays optional in the signature, and the
  "mandatory in practice" guarantee instead comes from
  ``EngagementService`` never calling it with anything but its own,
  non-``None`` organization id.
- ``get_for_organization``/``update_for_organization`` are new,
  additive tenant-scoped methods rather than overrides of the inherited
  ``get(entity_id)``/``update(entity)`` (also declared by
  ``IRepository[Engagement]`` with no scope parameter, for the same LSP
  reason as ``list``). The inherited, unscoped ``get``/``update`` remain
  implemented only to satisfy ``IRepository``'s contract and for test
  cleanup -- ``EngagementService`` must never call them;
  ``get_for_organization``/``update_for_organization`` are the only
  tenant-safe path.
"""

from abc import ABC, abstractmethod
from typing import Sequence
from uuid import UUID

from app.domain.entities.engagement import Engagement
from app.domain.repositories.base import IRepository


class IEngagementRepository(IRepository[Engagement], ABC):
    @abstractmethod
    async def list(
        self, *, limit: int = 100, offset: int = 0, organization_id: UUID | None = None
    ) -> Sequence[Engagement]: ...

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
