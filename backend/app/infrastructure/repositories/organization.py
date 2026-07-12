"""Concrete async repository for the ``Organization`` aggregate.

Implements ``IOrganizationRepository`` directly rather than subclassing the
generic ``SQLAlchemyRepository``, mirroring ``SQLAlchemyDocumentRepository``:
every method maps explicitly between ``OrganizationModel`` (ORM, imported
aliased since the ORM class and the domain entity share the name
``Organization``) and the domain ``Organization`` via ``_to_domain`` -- the
ORM type never crosses the repository boundary.

``id``/``created_at`` are server-generated (``gen_random_uuid()`` /
``CURRENT_TIMESTAMP``), so ``create()`` never assigns them; they are only
populated on the returned domain entity after ``refresh()``.

``delete()`` satisfies the inherited ``IRepository`` contract but is not
exposed through ``OrganizationService`` or any route this sprint -- it
exists solely so integration tests can remove the exact rows they create.
"""

from typing import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domain.entities.organization import Organization
from app.domain.repositories.organization import IOrganizationRepository
from app.infrastructure.db.models.organization import Organization as OrganizationModel


def _to_domain(model: OrganizationModel) -> Organization:
    return Organization(id=model.id, name=model.name, created_at=model.created_at)


class SQLAlchemyOrganizationRepository(IOrganizationRepository):
    """Async, PostgreSQL-backed implementation of ``IOrganizationRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: UUID) -> Organization | None:
        model = await self._session.get(OrganizationModel, entity_id)
        return _to_domain(model) if model is not None else None

    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[Organization]:
        stmt = (
            select(OrganizationModel)
            .order_by(OrganizationModel.created_at.asc(), OrganizationModel.id.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [_to_domain(model) for model in result.scalars().all()]

    async def count(self) -> int:
        stmt = select(func.count()).select_from(OrganizationModel)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def create(self, entity: Organization) -> Organization:
        model = OrganizationModel(name=entity.name)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def update(self, entity: Organization) -> Organization:
        model = await self._session.get(OrganizationModel, entity.id)
        if model is None:
            raise NotFoundError(f"Organization {entity.id} not found")
        model.name = entity.name
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def delete(self, entity: Organization) -> None:
        model = await self._session.get(OrganizationModel, entity.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.commit()
