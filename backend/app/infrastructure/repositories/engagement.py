"""Concrete async repository for the ``Engagement`` aggregate.

Implements ``IEngagementRepository`` directly, mirroring
``SQLAlchemyOrganizationRepository``: every method maps explicitly between
``EngagementModel`` (ORM, imported aliased since the ORM class and the
domain entity share the name ``Engagement``) and the domain ``Engagement``
via ``_to_domain``. Deliberately contains no reference to ``organizations``
beyond the plain foreign-key column already present on ``EngagementModel``
-- existence-checking an ``organization_id`` belongs to
``EngagementService`` (via ``IOrganizationRepository``), never here.

``delete()`` satisfies the inherited ``IRepository`` contract but is not
exposed through ``EngagementService`` or any route this sprint -- it
exists solely so integration tests can remove the exact rows they create.
"""

from typing import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domain.entities.engagement import Engagement
from app.domain.repositories.engagement import IEngagementRepository
from app.infrastructure.db.models.engagement import Engagement as EngagementModel


def _to_domain(model: EngagementModel) -> Engagement:
    return Engagement(
        id=model.id,
        organization_id=model.organization_id,
        title=model.title,
        status=model.status,
        created_at=model.created_at,
    )


class SQLAlchemyEngagementRepository(IEngagementRepository):
    """Async, PostgreSQL-backed implementation of ``IEngagementRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: UUID) -> Engagement | None:
        model = await self._session.get(EngagementModel, entity_id)
        return _to_domain(model) if model is not None else None

    async def list(
        self, *, limit: int = 100, offset: int = 0, organization_id: UUID | None = None
    ) -> Sequence[Engagement]:
        stmt = (
            select(EngagementModel)
            .order_by(EngagementModel.created_at.asc(), EngagementModel.id.asc())
            .limit(limit)
            .offset(offset)
        )
        if organization_id is not None:
            stmt = stmt.where(EngagementModel.organization_id == organization_id)
        result = await self._session.execute(stmt)
        return [_to_domain(model) for model in result.scalars().all()]

    async def count(self, *, organization_id: UUID | None = None) -> int:
        stmt = select(func.count()).select_from(EngagementModel)
        if organization_id is not None:
            stmt = stmt.where(EngagementModel.organization_id == organization_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def create(self, entity: Engagement) -> Engagement:
        model = EngagementModel(
            organization_id=entity.organization_id, title=entity.title, status=entity.status
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def update(self, entity: Engagement) -> Engagement:
        model = await self._session.get(EngagementModel, entity.id)
        if model is None:
            raise NotFoundError(f"Engagement {entity.id} not found")
        model.organization_id = entity.organization_id
        model.title = entity.title
        model.status = entity.status
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def delete(self, entity: Engagement) -> None:
        model = await self._session.get(EngagementModel, entity.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.commit()
