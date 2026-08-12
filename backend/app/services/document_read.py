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

``embedding_provider``/``embedding_model``/``embedding_model_version``
(constructor-supplied, mirroring ``EmbeddingGenerationService``'s own
identity parameters) are the app's one currently configured embedding
identity. Every read forwards them to the repository so each
document's ``embedding_summary`` reflects only that identity's
attempts -- never a sum across every (provider, model, model_version)
a document happens to have historical rows under, e.g. from before a
provider/model configuration change.
"""

from typing import Sequence
from uuid import UUID

from app.core.exceptions import AuthorizationError, NotFoundError
from app.domain.entities.document_read_model import DocumentReadModel
from app.domain.entities.user import User
from app.domain.evidence.lifecycle import EvidenceStatus
from app.domain.repositories.document import IDocumentRepository
from app.domain.repositories.engagement import IEngagementRepository


class DocumentReadService:
    def __init__(
        self,
        document_repository: IDocumentRepository,
        engagement_repository: IEngagementRepository,
        *,
        embedding_provider: str,
        embedding_model: str,
        embedding_model_version: str,
    ) -> None:
        self._document_repository = document_repository
        self._engagement_repository = engagement_repository
        self._embedding_provider = embedding_provider
        self._embedding_model = embedding_model
        self._embedding_model_version = embedding_model_version

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
        evidence_status: EvidenceStatus | None = None,
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
            evidence_status=evidence_status,
            limit=limit,
            offset=offset,
            embedding_provider=self._embedding_provider,
            embedding_model=self._embedding_model,
            embedding_model_version=self._embedding_model_version,
        )
        # Same filters as the page above, so `total` counts the filtered
        # set the caller is paging through -- a review queue's "12
        # pending" must not silently mean "12 documents in total".
        total = await self._document_repository.count_for_organization(
            organization_id=organization_id,
            engagement_id=engagement_id,
            processing_status=processing_status,
            evidence_status=evidence_status,
        )
        return items, total

    async def get(self, document_id: UUID, current_user: User) -> DocumentReadModel:
        organization_id = self._require_user_organization(current_user)
        document = await self._document_repository.get_read_model_for_organization(
            document_id,
            organization_id=organization_id,
            embedding_provider=self._embedding_provider,
            embedding_model=self._embedding_model,
            embedding_model_version=self._embedding_model_version,
        )
        if document is None:
            raise NotFoundError(f"Document {document_id} not found")
        return document
