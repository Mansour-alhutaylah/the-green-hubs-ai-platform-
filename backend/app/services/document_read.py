"""Tenant-safe Document read use cases: list and detail.

Sprint 3 (Document Read API Foundation). Mirrors ``EngagementService``'s
shape exactly: every method derives tenant scope from ``current_user``
(never a client-supplied value), raising ``AuthorizationError`` (403) if
the caller has no organization at all.

A client-supplied ``engagement_id`` filter is validated against
``IEngagementRepository.get_for_organization`` before it is ever handed
to the document repository -- a missing or foreign-tenant engagement
raises ``NotFoundError`` (404), indistinguishable from any other
nonexistent resource, never revealing whether the engagement exists
under a different organization.
"""

from typing import Sequence
from uuid import UUID

from app.core.exceptions import AuthorizationError, NotFoundError
from app.domain.entities.document_read_model import DocumentReadModel
from app.domain.entities.user import User
from app.domain.repositories.document import IDocumentRepository
from app.domain.repositories.engagement import IEngagementRepository


class DocumentReadService:
    def __init__(
        self,
        document_repository: IDocumentRepository,
        engagement_repository: IEngagementRepository,
    ) -> None:
        self._document_repository = document_repository
        self._engagement_repository = engagement_repository

    def _require_user_organization(self, current_user: User) -> UUID:
        if current_user.organization_id is None:
            raise AuthorizationError("User has no organization")
        return current_user.organization_id

    async def list(
        self,
        current_user: User,
        *,
        engagement_id: UUID | None,
        processing_status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[DocumentReadModel], int]:
        organization_id = self._require_user_organization(current_user)
        if engagement_id is not None:
            engagement = await self._engagement_repository.get_for_organization(
                engagement_id, organization_id=organization_id
            )
            if engagement is None:
                raise NotFoundError(f"Engagement {engagement_id} not found")
        items = await self._document_repository.list_read_models_for_organization(
            organization_id=organization_id,
            engagement_id=engagement_id,
            processing_status=processing_status,
            limit=limit,
            offset=offset,
        )
        total = await self._document_repository.count_for_organization(
            organization_id=organization_id,
            engagement_id=engagement_id,
            processing_status=processing_status,
        )
        return items, total

    async def get(self, document_id: UUID, current_user: User) -> DocumentReadModel:
        organization_id = self._require_user_organization(current_user)
        document = await self._document_repository.get_read_model_for_organization(
            document_id, organization_id=organization_id
        )
        if document is None:
            raise NotFoundError(f"Document {document_id} not found")
        return document
