"""Tenant-safe vector retrieval use case: semantic search over completed
chunk embeddings, scoped to the caller's own organization.

``organization_id`` is always derived from ``current_user`` -- never
accepted as a method parameter -- so there is no code path through which
a caller could search another tenant's embeddings. Optional
``engagement_id``/``document_id`` filters are ownership-checked against
the caller's organization before ever reaching the repository, using the
same indistinguishable-404 convention as Organization/Engagement
(Sprint 3.5.1) and Document Processing.

MVP Slice 3 (Organization Data Isolation): those two filter checks now
use the tenant-scoped ``get_for_organization`` on each repository
instead of an unscoped fetch followed by an in-memory comparison. The
document check in particular collapses from three statements (load
document, load its engagement, compare organizations) to one, because
the ownership chain is resolved by the repository's SQL join -- the
foreign row is never loaded into the process at all.

Retrieval itself was already tenant-safe and is unchanged: the
``organization_id`` predicate sits in the same ``WHERE`` clause as the
pgvector ``ORDER BY ... <=> ...``, so cross-tenant rows are never
candidates for ranking rather than being filtered out afterwards.
"""

from typing import Sequence
from uuid import UUID

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.domain.embedding_provider import EmbeddingProvider
from app.domain.entities.user import User
from app.domain.entities.vector_search_result import VectorSearchResult
from app.domain.repositories.document import IDocumentRepository
from app.domain.repositories.document_chunk_embedding import IDocumentChunkEmbeddingRepository
from app.domain.repositories.engagement import IEngagementRepository

_MAX_TOP_K = 50


class VectorRetrievalService:
    def __init__(
        self,
        embedding_repository: IDocumentChunkEmbeddingRepository,
        engagement_repository: IEngagementRepository,
        document_repository: IDocumentRepository,
        provider: EmbeddingProvider,
        *,
        provider_name: str,
        model: str,
        model_version: str,
    ) -> None:
        self._embedding_repository = embedding_repository
        self._engagement_repository = engagement_repository
        self._document_repository = document_repository
        self._provider = provider
        self._provider_name = provider_name
        self._model = model
        self._model_version = model_version

    async def search(
        self,
        current_user: User,
        *,
        query: str,
        top_k: int,
        engagement_id: UUID | None = None,
        document_id: UUID | None = None,
    ) -> Sequence[VectorSearchResult]:
        if current_user.organization_id is None:
            raise AuthorizationError("User has no organization")
        organization_id = current_user.organization_id

        if not query.strip():
            raise ValidationError("query must not be empty")
        if not (1 <= top_k <= _MAX_TOP_K):
            raise ValidationError(f"top_k must be between 1 and {_MAX_TOP_K}")

        if engagement_id is not None:
            engagement = await self._engagement_repository.get_for_organization(
                engagement_id, organization_id=organization_id
            )
            if engagement is None:
                raise NotFoundError(f"Engagement {engagement_id} not found")

        if document_id is not None:
            document = await self._document_repository.get_for_organization(
                document_id, organization_id=organization_id
            )
            if document is None:
                raise NotFoundError(f"Document {document_id} not found")
            if engagement_id is not None and document.engagement_id != engagement_id:
                raise ValidationError("document does not belong to the specified engagement")

        [query_embedding] = await self._provider.embed_texts([query])

        return await self._embedding_repository.search(
            organization_id=organization_id,
            provider=self._provider_name,
            model=self._model,
            model_version=self._model_version,
            query_vector=query_embedding.vector,
            top_k=top_k,
            engagement_id=engagement_id,
            document_id=document_id,
        )
