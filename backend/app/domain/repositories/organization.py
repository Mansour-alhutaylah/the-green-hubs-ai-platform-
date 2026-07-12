"""Abstract repository interface for ``Organization`` entities.

Extends the generic ``IRepository`` CRUD contract with ``count()``, which a
generic interface cannot express and which the list-endpoint's pagination
total requires. ``delete()`` is inherited from ``IRepository`` and is
implemented at the infrastructure layer solely so integration tests can
remove the exact rows they create -- Organization hard deletion is not a
supported application capability this sprint (``OrganizationService``
deliberately does not expose it).
"""

from abc import ABC, abstractmethod

from app.domain.entities.organization import Organization
from app.domain.repositories.base import IRepository


class IOrganizationRepository(IRepository[Organization], ABC):
    @abstractmethod
    async def count(self) -> int: ...
