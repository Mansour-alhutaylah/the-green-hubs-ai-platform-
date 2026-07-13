"""Organization business logic / use cases.

Sprint 3.5.1 (Tenant Isolation & API Security): every method now takes
``current_user`` and enforces the tenant boundary here, since
``Organization.id`` is itself the tenant identifier -- there is no
separate "owner" column for a repository-level SQL predicate to filter
on (unlike ``Engagement``, see ``EngagementService``). A caller may only
ever see, read, or update their own organization; a mismatched or
missing id is deliberately handled identically (``NotFoundError``), so a
cross-tenant probe cannot be distinguished from a nonexistent one.

Organization creation is temporarily disabled for every caller: there is
no approved provisioning/RBAC design yet for who may create an
organization or how its creator would be attached to it (``User.
organization_id`` is assigned by a separate process this codebase does
not implement yet). This is a deliberate, explicit MVP restriction --
not a placeholder for an invented owner/admin rule.
"""

from typing import Sequence
from uuid import UUID

from app.core.exceptions import AuthorizationError, NotFoundError
from app.domain.entities.organization import Organization
from app.domain.entities.user import User
from app.domain.repositories.organization import IOrganizationRepository


class OrganizationService:
    def __init__(self, repository: IOrganizationRepository) -> None:
        self._repository = repository

    async def create(self, name: str, current_user: User) -> Organization:
        raise AuthorizationError("Organization creation is not available in this phase.")

    async def get(self, organization_id: UUID, current_user: User) -> Organization:
        self._require_own_organization(organization_id, current_user)
        return await self._get_or_404(organization_id)

    async def list(
        self, current_user: User, *, page: int, page_size: int
    ) -> tuple[Sequence[Organization], int]:
        own_organization_id = self._require_user_organization(current_user)
        organization = await self._get_or_404(own_organization_id)
        offset = (page - 1) * page_size
        items = [organization] if offset == 0 else []
        return items, 1

    async def update(self, organization_id: UUID, name: str, current_user: User) -> Organization:
        self._require_own_organization(organization_id, current_user)
        existing = await self._get_or_404(organization_id)
        return await self._repository.update(
            Organization(id=existing.id, name=name, created_at=existing.created_at)
        )

    async def _get_or_404(self, organization_id: UUID) -> Organization:
        organization = await self._repository.get(organization_id)
        if organization is None:
            raise NotFoundError(f"Organization {organization_id} not found")
        return organization

    def _require_user_organization(self, current_user: User) -> UUID:
        if current_user.organization_id is None:
            raise AuthorizationError("User has no organization")
        return current_user.organization_id

    def _require_own_organization(self, organization_id: UUID, current_user: User) -> None:
        own_organization_id = self._require_user_organization(current_user)
        if organization_id != own_organization_id:
            # Deliberately NotFoundError, not AuthorizationError: a
            # cross-tenant id must be indistinguishable from a
            # nonexistent one, so this never reaches the repository at
            # all for the mismatched-id case.
            raise NotFoundError(f"Organization {organization_id} not found")
