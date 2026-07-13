"""Embedding generation use case: idempotently generates embeddings for a
PROCESSED document's chunks using the configured provider/model identity.

Pipeline per chunk: classify against any existing
(chunk_id, provider, model, model_version) row -- no row (claim), FAILED
with matching content (retry), PROCESSING with matching content (attempt
stale reclaim; the repository's own query decides whether it is
genuinely stale, not a pre-check here), COMPLETED with matching content
(skip, already done), or any state with a mismatched content_hash
(conflict -- never overwritten, see ``IDocumentChunkEmbeddingRepository``).
Newly-claimed/retried/reclaimed rows are then embedded in
provider-request-sized rounds: each round's provider call is the unit of
atomicity for its own COMPLETED/FAILED outcome (see
``mark_completed``/``mark_failed``) -- one round failing never affects
an earlier round's already-committed COMPLETED rows.

Cross-tenant authorization mirrors ``DocumentProcessingService.process()``'s
existing checks for document/engagement existence and organization-null
handling, but returns an indistinguishable 404 (not 403) for a
cross-tenant document, matching the newer, information-leak-safe
convention Sprint 3.5.1 established for Organization/Engagement -- a
deliberate improvement over Sprint 3.5's own, now-superseded, 403-on-
mismatch behavior.
"""

import hashlib
from dataclasses import dataclass
from uuid import UUID

from app.core.exceptions import AuthorizationError, InvalidStateTransitionError, NotFoundError
from app.domain.embedding_provider import EmbeddingProvider, EmbeddingProviderError
from app.domain.entities.user import User
from app.domain.repositories.document import IDocumentRepository
from app.domain.repositories.document_chunk import IDocumentChunkRepository
from app.domain.repositories.document_chunk_embedding import IDocumentChunkEmbeddingRepository
from app.domain.repositories.engagement import IEngagementRepository

_SAFE_ERROR_MESSAGES = {
    "EmbeddingAuthenticationError": "Embedding provider authentication failed",
    "EmbeddingProviderTimeoutError": "Embedding provider timed out",
    "EmbeddingProviderUnavailableError": "Embedding provider unavailable",
    "EmbeddingMalformedResponseError": "Embedding provider returned an unexpected response",
    "EmbeddingResultCountMismatchError": (
        "Embedding provider returned an unexpected number of results"
    ),
    "EmbeddingDimensionMismatchError": (
        "Embedding provider returned a vector of unexpected dimension"
    ),
    "EmbeddingValidationError": "Embedding request was invalid",
}


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _safe_error_message(exc: EmbeddingProviderError) -> str:
    return _SAFE_ERROR_MESSAGES.get(type(exc).__name__, "Embedding generation failed")


@dataclass(frozen=True)
class EmbeddingGenerationSummary:
    document_id: UUID
    total_chunks: int
    newly_completed: int
    already_completed: int
    failed: int
    in_progress: int
    conflicts: int


class EmbeddingGenerationService:
    def __init__(
        self,
        document_repository: IDocumentRepository,
        engagement_repository: IEngagementRepository,
        chunk_repository: IDocumentChunkRepository,
        embedding_repository: IDocumentChunkEmbeddingRepository,
        provider: EmbeddingProvider,
        *,
        provider_name: str,
        model: str,
        model_version: str,
        embedding_dimension: int,
        max_batch_size: int,
        stale_after_seconds: int,
    ) -> None:
        self._document_repository = document_repository
        self._engagement_repository = engagement_repository
        self._chunk_repository = chunk_repository
        self._embedding_repository = embedding_repository
        self._provider = provider
        self._provider_name = provider_name
        self._model = model
        self._model_version = model_version
        self._embedding_dimension = embedding_dimension
        self._max_batch_size = max_batch_size
        self._stale_after_seconds = stale_after_seconds

    async def generate_for_document(
        self, document_id: UUID, current_user: User
    ) -> EmbeddingGenerationSummary:
        document = await self._document_repository.get(document_id)
        if document is None:
            raise NotFoundError(f"Document {document_id} not found")
        engagement = await self._engagement_repository.get(document.engagement_id)
        if engagement is None:
            raise NotFoundError(f"Engagement {document.engagement_id} not found")
        if current_user.organization_id is None:
            raise AuthorizationError("User has no organization")
        if (
            engagement.organization_id is None
            or engagement.organization_id != current_user.organization_id
        ):
            raise NotFoundError(f"Document {document_id} not found")
        if document.processing_status != "PROCESSED":
            raise InvalidStateTransitionError(
                "Document must be processed before embeddings can be generated."
            )

        chunks = await self._chunk_repository.get_by_document(document_id)
        chunk_by_id = {chunk.id: chunk for chunk in chunks if chunk.id is not None}
        chunk_ids = list(chunk_by_id.keys())
        content_hashes = {
            chunk_id: _content_hash(chunk_by_id[chunk_id].content) for chunk_id in chunk_ids
        }

        existing = await self._embedding_repository.get_existing(
            chunk_ids,
            provider=self._provider_name,
            model=self._model,
            model_version=self._model_version,
        )
        existing_by_chunk = {row.chunk_id: row for row in existing}

        already_completed = 0
        conflicts = 0
        in_progress = 0
        to_claim: list[UUID] = []
        to_retry: list[UUID] = []
        to_reclaim: list[UUID] = []

        for chunk_id in chunk_ids:
            row = existing_by_chunk.get(chunk_id)
            if row is None:
                to_claim.append(chunk_id)
                continue
            content_matches = row.content_hash == content_hashes[chunk_id]
            if row.status == "COMPLETED":
                already_completed += 1 if content_matches else 0
                conflicts += 0 if content_matches else 1
            elif row.status == "FAILED":
                if content_matches:
                    assert row.id is not None
                    to_retry.append(row.id)
                else:
                    conflicts += 1
            elif row.status == "PROCESSING":
                if content_matches:
                    assert row.id is not None
                    to_reclaim.append(row.id)
                else:
                    conflicts += 1

        claimed = await self._embedding_repository.claim_new(
            to_claim,
            provider=self._provider_name,
            model=self._model,
            model_version=self._model_version,
            embedding_dimension=self._embedding_dimension,
            content_hashes=content_hashes,
        )
        in_progress += len(to_claim) - len(claimed)

        retried = await self._embedding_repository.retry_failed(to_retry)
        in_progress += len(to_retry) - len(retried)

        reclaimed = await self._embedding_repository.reclaim_stale(
            to_reclaim, stale_after_seconds=self._stale_after_seconds
        )
        in_progress += len(to_reclaim) - len(reclaimed)

        eligible = [*claimed, *retried, *reclaimed]

        newly_completed = 0
        failed = 0
        for start in range(0, len(eligible), self._max_batch_size):
            batch = eligible[start : start + self._max_batch_size]
            texts = [chunk_by_id[row.chunk_id].content for row in batch]
            try:
                results = await self._provider.embed_texts(texts)
            except EmbeddingProviderError as exc:
                batch_ids = [row.id for row in batch if row.id is not None]
                await self._embedding_repository.mark_failed(
                    batch_ids, error_message=_safe_error_message(exc)
                )
                failed += len(batch)
                continue
            resolved = [
                (row.id, result.vector)
                for row, result in zip(batch, results)
                if row.id is not None
            ]
            await self._embedding_repository.mark_completed(resolved)
            newly_completed += len(batch)

        return EmbeddingGenerationSummary(
            document_id=document_id,
            total_chunks=len(chunk_ids),
            newly_completed=newly_completed,
            already_completed=already_completed,
            failed=failed,
            in_progress=in_progress,
            conflicts=conflicts,
        )
