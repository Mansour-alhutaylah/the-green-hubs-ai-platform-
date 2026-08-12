"""Abstract repository interface for ``DocumentChunkEmbedding`` records.

Deliberately does not extend the generic ``IRepository[T]`` -- mirroring
``IExtractedTextRepository``/``IDocumentChunkRepository``'s own
precedent: this is not a simple CRUD aggregate but a set of atomic,
batch-oriented state transitions (claim / retry / reclaim-stale /
resolve) plus a tenant-scoped search, each with its own concurrency and
transaction-boundary contract documented per method below.

Every method that creates or transitions rows commits immediately (never
just flushes) -- the same rationale as ``IDocumentRepository.
begin_processing()``: these are the atomic facts other concurrent
requests must observe right away to avoid duplicate provider calls or
duplicate rows, not intermediate state a caller's own transaction should
be able to roll back.

Tenant lineage (``document_id``/``engagement_id``/``organization_id``)
is never accepted as an independent parameter on any method here --
only ``chunk_id`` is. Concrete implementations must derive the other
three from ``chunk_id``'s real ``document_chunks -> documents ->
engagements`` ownership chain at claim time (see
``SQLAlchemyDocumentChunkEmbeddingRepository``), and must never write
them again afterward.

MVP Slice 3 (Organization Data Isolation) adds the complementary half of
that rule: every method now takes the caller's trusted
``organization_id`` as a mandatory keyword-only *constraint*. Derivation
still decides what a row's lineage **is**; ``organization_id`` decides
which rows this caller may touch **at all**. The two are deliberately
different jobs -- before this slice, ``retry_failed``/``reclaim_stale``/
``mark_completed``/``mark_failed`` located rows by bare embedding id with
no tenant predicate whatsoever, so their safety rested entirely on an
in-application check performed several statements earlier in
``EmbeddingGenerationService``. The predicate now lives in the SQL, where
a future caller cannot forget it.

``organization_id`` is never used to *populate* a column here -- only to
filter -- so this does not weaken the derive-never-trust invariant above:
a caller that supplies its own organization with someone else's
``chunk_id`` still matches no rows.
"""

from abc import ABC, abstractmethod
from typing import Mapping, Sequence
from uuid import UUID

from app.domain.entities.document_chunk_embedding import DocumentChunkEmbedding
from app.domain.entities.vector_search_result import VectorSearchResult


class IDocumentChunkEmbeddingRepository(ABC):
    @abstractmethod
    async def claim_new(
        self,
        chunk_ids: Sequence[UUID],
        *,
        organization_id: UUID,
        provider: str,
        model: str,
        model_version: str,
        embedding_dimension: int,
        content_hashes: Mapping[UUID, str],
    ) -> Sequence[DocumentChunkEmbedding]:
        """Atomically claims chunks that have no existing row for this
        (provider, model, model_version) identity: an ``INSERT ...
        SELECT ... ON CONFLICT (chunk_id, provider, model, model_version)
        DO NOTHING`` that derives document_id/engagement_id/
        organization_id from each chunk's real lineage in the same
        statement, committed immediately. Chunks that already have a row
        (won by this call or a concurrent one) are silently excluded from
        the returned set -- callers determine existing-row state via
        ``get_existing()`` first and must not call this for chunks known
        to already have a row.

        The selecting join additionally requires the derived lineage's
        organization to equal ``organization_id``, so a ``chunk_id``
        belonging to another tenant inserts nothing at all rather than
        creating a row (and a paid provider call) against their data."""
        ...

    @abstractmethod
    async def get_existing(
        self,
        chunk_ids: Sequence[UUID],
        *,
        organization_id: UUID,
        provider: str,
        model: str,
        model_version: str,
    ) -> Sequence[DocumentChunkEmbedding]:
        """Returns whatever rows already exist for these chunks under this
        exact (provider, model, model_version) identity *and* this
        organization, regardless of status -- the caller classifies each
        as already-completed / conflicting / retriable / in-progress /
        stale before deciding what to claim, retry, or reclaim."""
        ...

    @abstractmethod
    async def retry_failed(
        self, embedding_ids: Sequence[UUID], *, organization_id: UUID
    ) -> Sequence[DocumentChunkEmbedding]:
        """Atomically transitions FAILED -> PROCESSING for retry: resets
        ``processing_started_at``, increments ``attempt_count``, clears
        ``error_message``, explicitly sets ``updated_at``. A row that is
        no longer FAILED when this runs (raced), or that belongs to
        another organization, is excluded from the returned set.
        Committed immediately."""
        ...

    @abstractmethod
    async def reclaim_stale(
        self,
        embedding_ids: Sequence[UUID],
        *,
        organization_id: UUID,
        stale_after_seconds: int,
    ) -> Sequence[DocumentChunkEmbedding]:
        """Atomically reclaims PROCESSING rows whose ``processing_started_at``
        is older than ``stale_after_seconds``: resets
        ``processing_started_at`` to now, increments ``attempt_count``,
        clears ``error_message``, keeps ``status = 'PROCESSING'``,
        explicitly sets ``updated_at``. The staleness check and the
        update happen in the same conditional statement, so a row that
        is not actually stale (or was already reclaimed by a concurrent
        caller, or belongs to another organization) is never reclaimed
        twice -- it is simply excluded from the returned set. Committed
        immediately."""
        ...

    @abstractmethod
    async def mark_completed(
        self, results: Sequence[tuple[UUID, Sequence[float]]], *, organization_id: UUID
    ) -> None:
        """Resolves a batch of claimed rows (by embedding id) to COMPLETED
        with their corresponding vectors, explicitly setting
        ``updated_at``. Represents the resolution of one successful
        provider-request batch -- committed immediately, as its own
        transaction, after the external call has already returned. Rows
        outside ``organization_id`` are never written."""
        ...

    @abstractmethod
    async def mark_failed(
        self, embedding_ids: Sequence[UUID], *, organization_id: UUID, error_message: str
    ) -> None:
        """Resolves a batch of claimed rows to FAILED with one shared,
        already-sanitized error message -- the whole provider-request
        batch failed together, so every row in it gets the same reason.
        Explicitly sets ``updated_at``. Rows outside ``organization_id``
        are never written. Committed immediately."""
        ...

    @abstractmethod
    async def search(
        self,
        *,
        organization_id: UUID,
        provider: str,
        model: str,
        model_version: str,
        query_vector: Sequence[float],
        top_k: int,
        engagement_id: UUID | None = None,
        document_id: UUID | None = None,
    ) -> Sequence[VectorSearchResult]:
        """Tenant-, model-, status-, and evidence-scoped cosine-similarity
        search. The WHERE clause and the ORDER BY ... <=> ... vector
        distance both apply to ``document_chunk_embeddings`` in the same
        query -- never a global fetch filtered afterward in Python. Only
        ``status = 'COMPLETED'`` rows matching the exact (provider,
        model, model_version) identity are eligible; a query embedding
        is never compared against a different model's vectors even if
        the dimensions happen to match.

        MVP Slice 4 adds the evidence predicate: a chunk is a candidate
        only if its document is in a retrieval-eligible evidence state
        (``RETRIEVAL_ELIGIBLE_STATUSES``). Implementations must apply it
        *before* ranking and ``LIMIT``, in the same statement -- not to
        the returned page. Filtering a ranked page afterwards would let
        an unapproved document's stronger match consume a ``top_k`` slot
        and silently shrink the approved evidence the caller receives,
        which is the specific defect
        ``test_a_stronger_unverified_match_never_displaces_a_verified_one``
        exists to catch."""
        ...

    @abstractmethod
    async def delete(self, entity: DocumentChunkEmbedding) -> None:
        """Test-cleanup only -- not used by any service."""
        ...
