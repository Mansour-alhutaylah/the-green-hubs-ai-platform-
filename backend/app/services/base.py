"""Generic base service.

Demonstrates the Router -> Service -> Repository dependency direction: a
service is constructed with an ``IRepository`` (the domain abstraction, never
a concrete infrastructure class directly), so business logic in future,
concrete services never depends on SQLAlchemy or any other implementation
detail. This sprint's ``BaseService`` intentionally contains no business
logic -- it only proves the wiring works end-to-end.
"""

from typing import Generic, Sequence, TypeVar
from uuid import UUID

from app.domain.repositories.base import IRepository

EntityType = TypeVar("EntityType")


class BaseService(Generic[EntityType]):
    def __init__(self, repository: IRepository[EntityType]) -> None:
        self._repository = repository

    async def get(self, entity_id: UUID) -> EntityType | None:
        return await self._repository.get(entity_id)

    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[EntityType]:
        return await self._repository.list(limit=limit, offset=offset)
