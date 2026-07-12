"""Concrete async repository for the ``User`` profile aggregate.

Implements ``IUserRepository`` directly, mirroring
``SQLAlchemyOrganizationRepository``: ``_to_domain`` maps the ORM model
(imported aliased since it shares the name ``User`` with the domain
entity) to the domain ``User``. ``create``/``update``/``delete`` exist only
for ``IRepository`` interface completeness -- this sprint's authentication
flow only ever calls ``get()``; user creation/registration is out of scope.
"""

from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domain.entities.user import User
from app.domain.repositories.user import IUserRepository
from app.infrastructure.db.models.user import User as UserModel


def _to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        organization_id=model.organization_id,
        full_name=model.full_name,
        email=model.email,
        role=model.role,
        created_at=model.created_at,
    )


class SQLAlchemyUserRepository(IUserRepository):
    """Async, PostgreSQL-backed implementation of ``IUserRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: UUID) -> User | None:
        model = await self._session.get(UserModel, entity_id)
        return _to_domain(model) if model is not None else None

    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[User]:
        stmt = (
            select(UserModel)
            .order_by(UserModel.created_at.asc(), UserModel.id.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [_to_domain(model) for model in result.scalars().all()]

    async def create(self, entity: User) -> User:
        model = UserModel(
            id=entity.id,
            organization_id=entity.organization_id,
            full_name=entity.full_name,
            email=entity.email,
            role=entity.role,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def update(self, entity: User) -> User:
        model = await self._session.get(UserModel, entity.id)
        if model is None:
            raise NotFoundError(f"User {entity.id} not found")
        model.organization_id = entity.organization_id
        model.full_name = entity.full_name
        model.email = entity.email
        model.role = entity.role
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def delete(self, entity: User) -> None:
        model = await self._session.get(UserModel, entity.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.commit()
