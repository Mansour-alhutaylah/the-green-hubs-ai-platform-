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
"""

from abc import ABC, abstractmethod
from typing import Generic, Sequence, TypeVar
from uuid import UUID

EntityType = TypeVar("EntityType")


class IRepository(ABC, Generic[EntityType]):
    """Generic CRUD contract that any concrete repository must fulfill."""

    @abstractmethod
    async def get(self, entity_id: UUID) -> EntityType | None: ...

    @abstractmethod
    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[EntityType]: ...

    @abstractmethod
    async def create(self, entity: EntityType) -> EntityType: ...

    @abstractmethod
    async def update(self, entity: EntityType) -> EntityType: ...

    @abstractmethod
    async def delete(self, entity: EntityType) -> None: ...
