"""Abstract repository interface for ``Engagement`` entities.

Extends the generic ``IRepository`` CRUD contract with an
``organization_id`` filter on ``list``/``count`` (needed for the list
endpoint's optional filter) and ``count()`` (needed for pagination
totals) -- neither is expressible by the generic interface alone.
``delete()`` is inherited from ``IRepository`` and is implemented at the
infrastructure layer solely so integration tests can remove the exact
rows they create, mirroring ``IOrganizationRepository``.

This repository must never query ``organizations`` -- Organization
existence is checked in ``EngagementService`` via
``IOrganizationRepository``, not here.
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
    async def count(self, *, organization_id: UUID | None = None) -> int: ...
