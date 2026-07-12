"""Engagement business logic / use cases.

Mirrors ``OrganizationService``'s shape, with one addition: every
``create``/``update`` that touches ``organization_id`` first confirms the
referenced Organization exists via ``IOrganizationRepository`` --
deliberately kept out of ``IEngagementRepository`` (which must never query
``organizations``) and out of the request schema (which cannot reach the
database). ``NotFoundError`` is raised uniformly for both "Engagement
missing" and "Organization missing"; the message text disambiguates.

``update``'s ``title``/``status``/``organization_id`` parameters are
``None`` if and only if the caller omitted that field -- the request
schema (``EngagementUpdateRequest``) already rejects an explicit ``null``
for any of these with a 422 before this method is ever reached, so by the
time execution gets here ``None`` unambiguously means "leave unchanged".
"""

from typing import Sequence
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.domain.entities.engagement import Engagement
from app.domain.repositories.engagement import IEngagementRepository
from app.domain.repositories.organization import IOrganizationRepository


class EngagementService:
    def __init__(
        self,
        repository: IEngagementRepository,
        organization_repository: IOrganizationRepository,
    ) -> None:
        self._repository = repository
        self._organization_repository = organization_repository

    async def _require_organization(self, organization_id: UUID) -> None:
        organization = await self._organization_repository.get(organization_id)
        if organization is None:
            raise NotFoundError(f"Organization {organization_id} not found")

    async def create(self, organization_id: UUID, title: str, status: str) -> Engagement:
        await self._require_organization(organization_id)
        return await self._repository.create(
            Engagement(
                id=None,
                organization_id=organization_id,
                title=title,
                status=status,
                created_at=None,
            )
        )

    async def get(self, engagement_id: UUID) -> Engagement:
        engagement = await self._repository.get(engagement_id)
        if engagement is None:
            raise NotFoundError(f"Engagement {engagement_id} not found")
        return engagement

    async def list(
        self, *, page: int, page_size: int, organization_id: UUID | None = None
    ) -> tuple[Sequence[Engagement], int]:
        offset = (page - 1) * page_size
        items = await self._repository.list(
            limit=page_size, offset=offset, organization_id=organization_id
        )
        total = await self._repository.count(organization_id=organization_id)
        return items, total

    async def update(
        self,
        engagement_id: UUID,
        *,
        title: str | None,
        status: str | None,
        organization_id: UUID | None,
    ) -> Engagement:
        existing = await self.get(engagement_id)
        if organization_id is not None:
            await self._require_organization(organization_id)
        updated = Engagement(
            id=existing.id,
            organization_id=(
                organization_id if organization_id is not None else existing.organization_id
            ),
            title=title if title is not None else existing.title,
            status=status if status is not None else existing.status,
            created_at=existing.created_at,
        )
        return await self._repository.update(updated)
