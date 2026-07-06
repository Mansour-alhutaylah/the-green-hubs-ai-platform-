"""Concrete, generic SQLAlchemy repository implementing ``IRepository``.

All queries use SQLAlchemy's expression API with bound parameters -- no raw
SQL string building anywhere. This directly addresses two Hemaya
anti-patterns: ``main.py``'s raw SQL interleaved with ORM calls throughout,
and ``vector_store.py``'s fragile string-concatenated vector literals.

Future concrete repositories (e.g. ``DocumentRepository``) subclass this:

    class DocumentRepository(SQLAlchemyRepository[Document]):
        def __init__(self, session: AsyncSession) -> None:
            super().__init__(session, Document)
"""

from typing import Generic, Sequence, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.base import IRepository
from app.infrastructure.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class SQLAlchemyRepository(IRepository[ModelType], Generic[ModelType]):
    def __init__(self, session: AsyncSession, model: type[ModelType]) -> None:
        self._session = session
        self._model = model

    async def get(self, entity_id: UUID) -> ModelType | None:
        return await self._session.get(self._model, entity_id)

    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[ModelType]:
        stmt = select(self._model).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def create(self, entity: ModelType) -> ModelType:
        self._session.add(entity)
        await self._session.commit()
        await self._session.refresh(entity)
        return entity

    async def update(self, entity: ModelType) -> ModelType:
        await self._session.commit()
        await self._session.refresh(entity)
        return entity

    async def delete(self, entity: ModelType) -> None:
        await self._session.delete(entity)
        await self._session.commit()
