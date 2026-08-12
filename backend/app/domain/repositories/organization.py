"""Abstract repository interface for ``Organization`` entities.

An Organization row *is* the tenant root: its ``id`` is the tenant
identifier every other table's ownership chain terminates at. There is no
separate owner column for a predicate to filter on, so "scoped access" to
this table means exactly one thing -- you may read the organization whose
id equals your own trusted ``organization_id``, and no other.

``get_for_organization`` is named for that, and takes the trusted
organization id as its only argument. It is the sole read this interface
offers.

MVP Slice 3 closure -- deliberately absent:

* **no ``list``.** A global organization listing enumerates every tenant
  on the platform by name. It was inherited from ``IRepository``,
  implemented, and never called (``OrganizationService.list`` returns the
  caller's own organization and a hardcoded total of 1). It is now gone
  rather than left available.
* **no ``count``.** A global count discloses how many other organizations
  exist -- a smaller leak than ``list``, but the same kind, and equally
  unused.
* **no generic ``get``.** Renamed to ``get_for_organization`` so the call
  site reads as a scoped access rather than an arbitrary lookup by id.

Global organization administration is intentionally left unimplemented.
It requires a privileged system-administration model that this codebase
does not have and that no approved decision defines; inventing one to
justify keeping these methods would be the opposite of a security fix.

``delete()`` is inherited from ``IRepository`` and is implemented at the
infrastructure layer solely so integration tests can remove the exact rows
they create -- Organization hard deletion is not a supported application
capability (``OrganizationService`` deliberately does not expose it).
"""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.organization import Organization
from app.domain.repositories.base import IRepository


class IOrganizationRepository(IRepository[Organization], ABC):
    @abstractmethod
    async def get_for_organization(self, organization_id: UUID) -> Organization | None:
        """Read one organization by its own id.

        ``organization_id`` MUST be the caller's server-resolved
        ``User.organization_id`` (or, for an existence check, an id the
        service has already proven equal to it) -- never a client-supplied
        value used as authority. Because the id *is* the tenant scope,
        passing the trusted value is what makes this call tenant-safe.

        Returns ``None`` for an unknown id.
        """
        ...
