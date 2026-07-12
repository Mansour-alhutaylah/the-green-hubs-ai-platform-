"""Organization business logic / use cases.

First concrete (non-generic) service in the codebase. Name normalization
(strip whitespace, reject blank) is enforced once, at the request-schema
boundary (``app/schemas/organization.py``) -- this service trusts that a
``name`` it receives has already been validated, the same way
``SQLAlchemyDocumentRepository`` trusts the domain entities it is given.

Constructed with an ``IOrganizationRepository`` (the domain abstraction,
never the concrete SQLAlchemy class), so nothing here depends on
SQLAlchemy or any other infrastructure detail. Deliberately has no
knowledge of "who" is calling -- authentication (Sprint 3.3) is added at
the router layer via a FastAPI dependency, not threaded through here.
"""

from typing import Sequence
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.domain.entities.organization import Organization
from app.domain.repositories.organization import IOrganizationRepository


class OrganizationService:
    def __init__(self, repository: IOrganizationRepository) -> None:
        self._repository = repository

    async def create(self, name: str) -> Organization:
        return await self._repository.create(Organization(id=None, name=name, created_at=None))

    async def get(self, organization_id: UUID) -> Organization:
        organization = await self._repository.get(organization_id)
        if organization is None:
            raise NotFoundError(f"Organization {organization_id} not found")
        return organization

    async def list(self, *, page: int, page_size: int) -> tuple[Sequence[Organization], int]:
        offset = (page - 1) * page_size
        items = await self._repository.list(limit=page_size, offset=offset)
        total = await self._repository.count()
        return items, total

    async def update(self, organization_id: UUID, name: str) -> Organization:
        existing = await self.get(organization_id)
        return await self._repository.update(
            Organization(id=existing.id, name=name, created_at=existing.created_at)
        )
