"""Abstract repository interface.

This is the Dependency Inversion boundary of the whole application: the
``services`` layer depends only on ``IRepository`` (defined here, in the
innermost layer), never on a concrete database implementation. Concrete
implementations live in ``infrastructure/repositories`` and satisfy this
interface.

This directly addresses a Hemaya anti-pattern: its ``main.py`` routes queried
``models.X`` (SQLAlchemy ORM classes) directly, with no repository boundary
at all, and a generic ``ENTITY_MAP`` dict drove reflection-based CRUD instead
of typed, purpose-built repositories.

MVP Slice 3 closure: this contract deliberately declares **no ``get`` and
no ``list``.**

Both used to be here, and both were unscoped by construction: a generic
``get(entity_id)`` returns whatever row carries that id, and a generic
``list(limit, offset)`` enumerates a whole table -- neither can express
"and only if it belongs to the caller's organization", because a generic
contract has no idea which of its implementors are tenant-owned. Inheriting
them gave every tenant-owned repository a silent cross-tenant read path
that no route used but any future caller could have.

Reads are therefore declared per interface, named for the scope they
enforce, so the unsafe shape is *structurally unavailable* rather than
merely unused:

* tenant-owned entities expose ``get_for_organization(id, *,
  organization_id)`` (see ``IDocumentRepository``/``IEngagementRepository``)
  -- the tenant predicate is mandatory and lives in the SQL;
* ``IOrganizationRepository`` exposes ``get_for_organization(organization_id)``
  -- the organization *is* the tenant root, so its id is itself the scope;
* ``IUserRepository`` exposes only ``get_by_authenticated_id`` -- the
  narrowly documented authentication bootstrap, see that module.

What remains here is the single-entity write surface. ``update`` and
``delete`` are not tenant bypasses in the same way: they take an entity the
caller must already hold, which it can only have obtained through one of
the scoped reads above. ``create`` assigns ownership from server context.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

EntityType = TypeVar("EntityType")


class IRepository(ABC, Generic[EntityType]):
    """Generic single-entity write contract.

    Deliberately has no ``get``/``list`` -- see the module docstring.
    """

    @abstractmethod
    async def create(self, entity: EntityType) -> EntityType: ...

    @abstractmethod
    async def update(self, entity: EntityType) -> EntityType: ...

    @abstractmethod
    async def delete(self, entity: EntityType) -> None: ...
