"""Abstract repository interface for the ``AnalysisRun`` /
``AnalysisSourceReference`` aggregate.

Mirrors ``IDocumentChunkEmbeddingRepository``'s shape: not a simple CRUD
aggregate but a set of atomic, single-row state transitions (claim-or-get
/ retry / reclaim-stale / resolve) plus citation persistence, each with
its own concurrency contract documented per method below. Every method
that creates or transitions a row commits immediately (never just
flushes) -- these are atomic facts other concurrent requests (racing on
the same ``(organization_id, request_hash)``) must observe right away.

Citation lineage (``document_id``/``engagement_id``/``organization_id``
on each ``AnalysisSourceReference``) is never accepted as an independent
parameter -- only ``chunk_id`` is. ``add_citations`` derives the other
three from ``chunk_id``'s real ``document_chunks -> documents ->
engagements`` ownership chain, and only inserts a citation when that
derived chain's ``organization_id`` matches the analysis run's own
``organization_id`` -- the same "derive, never trust" invariant
``document_chunk_embeddings`` established in Sprint 3.6A, now closing
the specific risk Mandatory Correction 2 is about: an LLM-cited source
key must resolve to a chunk this tenant's run is actually entitled to.

MVP Slice 3 (Organization Data Isolation): every remaining method that
addressed a run by bare id -- ``retry_failed``, ``reclaim_stale``,
``mark_completed``, ``mark_failed``, ``mark_insufficient_evidence`` and
``get_citations`` -- now takes the caller's trusted ``organization_id``
as a mandatory keyword-only constraint, matching ``get_by_id``'s
long-standing shape. ``get_citations`` is the sharpest of these: a
citation row carries ``quoted_snippet``, verbatim text from the source
document, so an unscoped read of it by run id would have disclosed
another tenant's document content directly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence
from uuid import UUID

from app.domain.entities.analysis_run import AnalysisRun
from app.domain.entities.analysis_source_reference import AnalysisSourceReference


@dataclass(frozen=True)
class NewCitation:
    chunk_id: UUID
    citation_order: int
    relevance_score: Decimal
    char_start: int
    char_end: int
    quoted_snippet: str


class IAnalysisRunRepository(ABC):
    @abstractmethod
    async def claim_or_get(
        self,
        *,
        organization_id: UUID,
        engagement_id: UUID,
        document_id: UUID | None,
        requested_by_user_id: UUID,
        analysis_type: str,
        query_text: str | None,
        provider: str,
        model: str,
        prompt_template_version: str,
        output_schema_version: str,
        temperature: Decimal,
        retrieval_top_k: int,
        embedding_provider: str,
        embedding_model: str,
        embedding_model_version: str,
        minimum_relevance_score: Decimal,
        request_hash: str,
    ) -> tuple[AnalysisRun, bool]:
        """Atomically claims a new run via ``INSERT ... ON CONFLICT
        (organization_id, request_hash) DO NOTHING RETURNING ...``. If a
        row was inserted, returns ``(run, True)``. If the insert
        conflicted -- an identical request already exists for this
        organization, in any status -- returns the existing row as
        ``(run, False)`` instead, read back in the same call after the
        conflicting insert's transaction has resolved. Never returns a
        row belonging to a different organization: the conflict target
        is itself tenant-scoped. Committed immediately."""
        ...

    @abstractmethod
    async def get_by_id(
        self, analysis_run_id: UUID, *, organization_id: UUID
    ) -> AnalysisRun | None:
        """Tenant-scoped read. Returns ``None`` for a foreign-tenant id,
        indistinguishable from a nonexistent id."""
        ...

    @abstractmethod
    async def retry_failed(
        self, analysis_run_id: UUID, *, organization_id: UUID
    ) -> AnalysisRun | None:
        """Atomically transitions FAILED -> PROCESSING for retry: resets
        ``processing_started_at``, increments ``attempt_count``, clears
        ``error_message``/``insufficient_evidence_reason``, explicitly
        sets ``updated_at``. Returns ``None`` if the row is no longer
        FAILED when this runs (raced by a concurrent retry) or belongs to
        another organization. Committed immediately."""
        ...

    @abstractmethod
    async def reclaim_stale(
        self, analysis_run_id: UUID, *, organization_id: UUID, stale_after_seconds: int
    ) -> AnalysisRun | None:
        """Atomically reclaims a PROCESSING row whose
        ``processing_started_at`` is older than ``stale_after_seconds``:
        resets ``processing_started_at`` to now, increments
        ``attempt_count``, keeps ``status = 'PROCESSING'``, explicitly
        sets ``updated_at``. The staleness check and the update happen in
        the same conditional statement, so a row that is not actually
        stale (or was already reclaimed by a concurrent caller, or
        belongs to another organization) is never reclaimed twice --
        returns ``None`` instead. Committed immediately."""
        ...

    @abstractmethod
    async def mark_completed(
        self,
        analysis_run_id: UUID,
        *,
        organization_id: UUID,
        structured_output: dict,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        total_tokens: int | None,
        estimated_cost: Decimal | None,
    ) -> None:
        """Resolves a claimed row to COMPLETED with its validated
        structured output and token usage, setting ``completed_at`` and
        ``updated_at``. Only transitions rows currently PROCESSING *and*
        owned by ``organization_id``. Committed immediately, after the
        external LLM call has already returned -- never called while any
        other transaction-scoped work is pending."""
        ...

    @abstractmethod
    async def mark_failed(
        self, analysis_run_id: UUID, *, organization_id: UUID, error_message: str
    ) -> None:
        """Resolves a claimed row to FAILED with an already-sanitized
        error message, clearing ``structured_output``. Only transitions
        rows currently PROCESSING and owned by ``organization_id``.
        Committed immediately."""
        ...

    @abstractmethod
    async def mark_insufficient_evidence(
        self, analysis_run_id: UUID, *, organization_id: UUID, reason: str
    ) -> None:
        """Resolves a claimed row to INSUFFICIENT_EVIDENCE with a
        required reason, clearing ``structured_output``, setting
        ``completed_at``. Only transitions rows currently PROCESSING.
        Committed immediately. Used both when retrieval itself returns no
        sufficiently relevant chunks (no LLM call made) and when the LLM
        itself judges the retrieved evidence insufficient."""
        ...

    @abstractmethod
    async def add_citations(
        self,
        analysis_run_id: UUID,
        *,
        organization_id: UUID,
        citations: Sequence[NewCitation],
    ) -> Sequence[AnalysisSourceReference]:
        """Inserts one ``analysis_source_references`` row per citation,
        deriving ``document_id``/``engagement_id``/``organization_id``
        from each ``chunk_id``'s real lineage rather than trusting any
        caller-supplied value. A citation whose derived organization does
        not match ``organization_id`` is silently excluded (defense in
        depth -- should never occur, since callers only ever cite chunks
        already returned by a tenant-scoped retrieval). Committed
        immediately."""
        ...

    @abstractmethod
    async def get_citations(
        self, analysis_run_id: UUID, *, organization_id: UUID
    ) -> Sequence[AnalysisSourceReference]:
        """Returns all persisted citations for a run, ordered by
        ``citation_order``. Tenant-scoped: a run id belonging to another
        organization yields an empty sequence, never its
        ``quoted_snippet`` text."""
        ...

    @abstractmethod
    async def delete(self, entity: AnalysisRun) -> None:
        """Test-cleanup only -- not used by any service."""
        ...
