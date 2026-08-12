"""Abstract repository interface for ``User`` profile entities.

MVP Slice 3 closure. This interface exposes exactly one read, and it is
the **authentication bootstrap exception** -- the single place in the
application where a tenant-owned row is read without a trusted
organization scope, because the scope does not exist yet at that moment.

The bootstrap, in full:

    verified JWT ``sub``  ->  get_by_authenticated_id(sub)  ->  User.organization_id

``get_by_authenticated_id`` is safe *only* because of what its argument
is. The caller (``app.api.deps.get_current_user``) does not choose it: it
is the subject claim of a Supabase-issued JWT whose signature, issuer and
audience ``SupabaseJWTVerifier`` has already validated. A caller can
therefore only ever retrieve the profile the token was minted for -- its
own. The row it returns is what *establishes* ``organization_id``;
requiring an organization scope to fetch it would be circular.

The method is named for that one job rather than being a generic ``get``
so the exception cannot be reused by accident. Nothing else may call it:
``tests/domain/architecture/test_tenant_scope_guard.py`` allows exactly
one call site (``deps.py``) and fails CI on any other.

Deliberately absent -- and these are the point of the closure:

* **no ``list``.** Bulk user enumeration is a global tenant bypass by
  definition: it returns every organization's members, with their names
  and email addresses. It was previously inherited from ``IRepository``,
  implemented, and unused; "unused" is not a security boundary, so it is
  gone. A future user-management feature must add an explicitly
  tenant-scoped method (``list_for_organization``) following
  ``IEngagementRepository``'s convention.
* **no generic ``get``.** Reading an arbitrary user by arbitrary id is
  not something this application needs, and offering it would make the
  bootstrap exception indistinguishable from ordinary access.

``create``/``update``/``delete`` are inherited from ``IRepository`` for
interface completeness and are not called by any service or route; user
creation/registration remains out of scope.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.user import User
from app.domain.repositories.base import IRepository


class IUserRepository(IRepository[User], ABC):
    @abstractmethod
    async def get_by_authenticated_id(self, user_id: UUID) -> User | None:
        """Load the profile of an already-authenticated principal.

        ``user_id`` MUST be the ``sub`` of a signature-verified JWT --
        never a value taken from a request body, query string, path
        parameter or header. Returns ``None`` when no application profile
        has been provisioned for that account, which the caller turns
        into ``ProfileNotProvisionedError``.

        See the module docstring for why this is the one read in the
        codebase that carries no organization scope.
        """
        ...
