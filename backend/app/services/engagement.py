"""Engagement business logic / use cases.

Sprint 3.5.1 (Tenant Isolation & API Security): every method now takes
``current_user`` and enforces the tenant boundary before touching the
repository. ``get``/``update`` use ``IEngagementRepository``'s
tenant-scoped ``get_for_organization``/``update_for_organization`` --
never the inherited, unscoped ``get``/``update`` -- so a cross-tenant
Engagement and a genuinely nonexistent one produce the exact same
``NotFoundError`` (404), without ever fetching the other tenant's row
into memory first.

Every ``create``/``update`` that touches ``organization_id`` still
confirms the referenced Organization exists via
``IOrganizationRepository`` (deliberately kept out of
``IEngagementRepository``, which must never query ``organizations``),
in addition to the new tenant check. ``NotFoundError`` is raised
uniformly for "Engagement missing" and "Organization missing"; the
message text disambiguates.

Cross-tenant creation and reassignment are both rejected with
``AuthorizationError`` (403), not ``NotFoundError``: unlike a read of an
existing resource, no resource's existence is being probed in either
case -- the caller is an already-identified, authenticated principal
attempting a disallowed action, not fishing for information about
something they can't see.

``update``'s ``title``/``status``/``organization_id`` parameters are
``None`` if and only if the caller omitted that field -- the request
schema (``EngagementUpdateRequest``) already rejects an explicit ``null``
for any of these with a 422 before this method is ever reached, so by the
time execution gets here ``None`` unambiguously means "leave unchanged".
A supplied ``organization_id`` equal to the caller's own organization is
accepted as a no-op; any other value is rejected outright -- there is no
role vocabulary this sprint to decide who, if anyone, may reassign an
Engagement across tenants, so nobody may.
"""

from typing import Sequence
from uuid import UUID

from app.core.exceptions import AuthorizationError, NotFoundError
from app.domain.entities.engagement import Engagement
from app.domain.entities.user import User
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

    async def _require_organization_exists(self, organization_id: UUID) -> None:
        organization = await self._organization_repository.get(organization_id)
        if organization is None:
            raise NotFoundError(f"Organization {organization_id} not found")

    def _require_user_organization(self, current_user: User) -> UUID:
        if current_user.organization_id is None:
            raise AuthorizationError("User has no organization")
        return current_user.organization_id

    async def create(
        self, organization_id: UUID, title: str, status: str, current_user: User
    ) -> Engagement:
        own_organization_id = self._require_user_organization(current_user)
        if organization_id != own_organization_id:
            raise AuthorizationError("Cannot create an Engagement for another organization")
        await self._require_organization_exists(organization_id)
        return await self._repository.create(
            Engagement(
                id=None,
                organization_id=organization_id,
                title=title,
                status=status,
                created_at=None,
            )
        )

    async def get(self, engagement_id: UUID, current_user: User) -> Engagement:
        own_organization_id = self._require_user_organization(current_user)
        engagement = await self._repository.get_for_organization(
            engagement_id, organization_id=own_organization_id
        )
        if engagement is None:
            raise NotFoundError(f"Engagement {engagement_id} not found")
        return engagement

    async def list(
        self,
        current_user: User,
        *,
        page: int,
        page_size: int,
        organization_id: UUID | None = None,
    ) -> tuple[Sequence[Engagement], int]:
        own_organization_id = self._require_user_organization(current_user)
        if organization_id is not None and organization_id != own_organization_id:
            raise AuthorizationError("Cannot list Engagements for another organization")
        offset = (page - 1) * page_size
        items = await self._repository.list(
            limit=page_size, offset=offset, organization_id=own_organization_id
        )
        total = await self._repository.count(organization_id=own_organization_id)
        return items, total

    async def update(
        self,
        engagement_id: UUID,
        *,
        title: str | None,
        status: str | None,
        organization_id: UUID | None,
        current_user: User,
    ) -> Engagement:
        own_organization_id = self._require_user_organization(current_user)
        existing = await self._repository.get_for_organization(
            engagement_id, organization_id=own_organization_id
        )
        if existing is None:
            raise NotFoundError(f"Engagement {engagement_id} not found")
        if organization_id is not None and organization_id != own_organization_id:
            raise AuthorizationError("Cannot reassign an Engagement to another organization")
        updated = Engagement(
            id=existing.id,
            organization_id=own_organization_id,
            title=title if title is not None else existing.title,
            status=status if status is not None else existing.status,
            created_at=existing.created_at,
        )
        return await self._repository.update_for_organization(
            updated, organization_id=own_organization_id
        )
