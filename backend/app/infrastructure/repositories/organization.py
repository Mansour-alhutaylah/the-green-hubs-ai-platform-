"""Concrete async repository for the ``Organization`` aggregate.

Implements ``IOrganizationRepository`` directly, mirroring
``SQLAlchemyDocumentRepository``: every method maps explicitly between
``OrganizationModel`` (ORM, imported aliased since the ORM class and the
domain entity share the name ``Organization``) and the domain
``Organization`` via ``_to_domain`` -- the ORM type never crosses the
repository boundary.

MVP Slice 3 closure: ``list()`` and ``count()`` have been **removed**.
Both were global across every tenant -- one enumerating all organizations
by name, the other disclosing how many exist -- and neither was called by
any service. ``get()`` became ``get_for_organization()``, which takes the
caller's own trusted organization id; since the organization id *is* the
tenant scope, that is what makes the read safe. See
``IOrganizationRepository``.

``id``/``created_at`` are server-generated (``gen_random_uuid()`` /
``CURRENT_TIMESTAMP``), so ``create()`` never assigns them; they are only
populated on the returned domain entity after ``refresh()``.

``delete()`` satisfies the inherited ``IRepository`` contract but is not
exposed through ``OrganizationService`` or any route this sprint -- it
exists solely so integration tests can remove the exact rows they create.
"""

from uuid import UUID

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

    async def get_for_organization(self, organization_id: UUID) -> Organization | None:
        model = await self._session.get(OrganizationModel, organization_id)
        return _to_domain(model) if model is not None else None

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
