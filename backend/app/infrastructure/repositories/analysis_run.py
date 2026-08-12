"""Concrete async repository for the ``AnalysisRun`` /
``AnalysisSourceReference`` aggregate.

Sprint 3.6B, RAG + Structured Sustainability Analysis Foundation. Every
write method commits immediately (never just flushes) -- the same
rationale as ``SQLAlchemyDocumentChunkEmbeddingRepository``: these are
atomic concurrency facts other concurrent requests (racing on the same
``(organization_id, request_hash)``, or reclaiming the same stale run)
must observe right away.

Raw ``text()`` SQL is used throughout, mirroring
``SQLAlchemyDocumentChunkEmbeddingRepository`` exactly, including its
``INSERT ... SELECT ... JOIN`` lineage-derivation shape for citations.
Bind parameters are never followed directly by a ``::type`` cast
shorthand -- always ``CAST(:param AS type)`` -- per this project's
established SQLAlchemy ``text()`` gotcha.

MVP Slice 3 (Organization Data Isolation): every statement here now
carries ``organization_id = :organization_id`` alongside the row id.
``claim_or_get``/``get_by_id``/``add_citations`` already did;
``retry_failed``, ``reclaim_stale``, the three ``mark_*`` transitions and
``get_citations`` did not. ``analysis_source_references.quoted_snippet``
holds verbatim source-document text, so ``get_citations`` in particular
was a direct content-disclosure path keyed on nothing but a run UUID.
"""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.analysis_run import AnalysisRun
from app.domain.entities.analysis_source_reference import AnalysisSourceReference
from app.domain.repositories.analysis_run import IAnalysisRunRepository, NewCitation

_RUN_COLUMNS = (
    "id, organization_id, engagement_id, document_id, requested_by_user_id, analysis_type, "
    "query_text, provider, model, prompt_template_version, output_schema_version, temperature, "
    "retrieval_top_k, embedding_provider, embedding_model, embedding_model_version, "
    "minimum_relevance_score, request_hash, status, structured_output, error_message, "
    "insufficient_evidence_reason, prompt_tokens, completion_tokens, total_tokens, "
    "estimated_cost, processing_started_at, attempt_count, created_at, updated_at, completed_at"
)

_CITATION_COLUMNS = (
    "id, analysis_run_id, chunk_id, document_id, engagement_id, organization_id, chunk_index, "
    "char_start, char_end, quoted_snippet, citation_order, relevance_score, created_at"
)


def _run_from_row(row) -> AnalysisRun:
    return AnalysisRun(
        id=row.id,
        organization_id=row.organization_id,
        engagement_id=row.engagement_id,
        document_id=row.document_id,
        requested_by_user_id=row.requested_by_user_id,
        analysis_type=row.analysis_type,
        query_text=row.query_text,
        provider=row.provider,
        model=row.model,
        prompt_template_version=row.prompt_template_version,
        output_schema_version=row.output_schema_version,
        temperature=row.temperature,
        retrieval_top_k=row.retrieval_top_k,
        embedding_provider=row.embedding_provider,
        embedding_model=row.embedding_model,
        embedding_model_version=row.embedding_model_version,
        minimum_relevance_score=row.minimum_relevance_score,
        request_hash=row.request_hash,
        status=row.status,
        structured_output=row.structured_output,
        error_message=row.error_message,
        insufficient_evidence_reason=row.insufficient_evidence_reason,
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        total_tokens=row.total_tokens,
        estimated_cost=row.estimated_cost,
        processing_started_at=row.processing_started_at,
        attempt_count=row.attempt_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
    )


def _citation_from_row(row) -> AnalysisSourceReference:
    return AnalysisSourceReference(
        id=row.id,
        analysis_run_id=row.analysis_run_id,
        chunk_id=row.chunk_id,
        document_id=row.document_id,
        engagement_id=row.engagement_id,
        organization_id=row.organization_id,
        chunk_index=row.chunk_index,
        char_start=row.char_start,
        char_end=row.char_end,
        quoted_snippet=row.quoted_snippet,
        citation_order=row.citation_order,
        relevance_score=row.relevance_score,
        created_at=row.created_at,
    )


class SQLAlchemyAnalysisRunRepository(IAnalysisRunRepository):
    """Async, PostgreSQL-backed implementation of ``IAnalysisRunRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
        result = await self._session.execute(
            text(
                f"""
                INSERT INTO analysis_runs
                  (organization_id, engagement_id, document_id, requested_by_user_id,
                   analysis_type, query_text, provider, model, prompt_template_version,
                   output_schema_version, temperature, retrieval_top_k, embedding_provider,
                   embedding_model, embedding_model_version, minimum_relevance_score,
                   request_hash, status)
                VALUES
                  (:organization_id, :engagement_id, :document_id, :requested_by_user_id,
                   :analysis_type, :query_text, :provider, :model, :prompt_template_version,
                   :output_schema_version, :temperature, :retrieval_top_k, :embedding_provider,
                   :embedding_model, :embedding_model_version, :minimum_relevance_score,
                   :request_hash, 'PROCESSING')
                ON CONFLICT (organization_id, request_hash) DO NOTHING
                RETURNING {_RUN_COLUMNS}
                """
            ),
            {
                "organization_id": organization_id,
                "engagement_id": engagement_id,
                "document_id": document_id,
                "requested_by_user_id": requested_by_user_id,
                "analysis_type": analysis_type,
                "query_text": query_text,
                "provider": provider,
                "model": model,
                "prompt_template_version": prompt_template_version,
                "output_schema_version": output_schema_version,
                "temperature": temperature,
                "retrieval_top_k": retrieval_top_k,
                "embedding_provider": embedding_provider,
                "embedding_model": embedding_model,
                "embedding_model_version": embedding_model_version,
                "minimum_relevance_score": minimum_relevance_score,
                "request_hash": request_hash,
            },
        )
        row = result.mappings().first()
        await self._session.commit()
        if row is not None:
            return _run_from_row(row), True

        existing = await self._session.execute(
            text(f"SELECT {_RUN_COLUMNS} FROM analysis_runs "
                 "WHERE organization_id = :organization_id AND request_hash = :request_hash"),
            {"organization_id": organization_id, "request_hash": request_hash},
        )
        existing_row = existing.mappings().first()
        assert existing_row is not None
        return _run_from_row(existing_row), False

    async def get_by_id(
        self, analysis_run_id: UUID, *, organization_id: UUID
    ) -> AnalysisRun | None:
        result = await self._session.execute(
            text(f"SELECT {_RUN_COLUMNS} FROM analysis_runs "
                 "WHERE id = :id AND organization_id = :organization_id"),
            {"id": analysis_run_id, "organization_id": organization_id},
        )
        row = result.mappings().first()
        return _run_from_row(row) if row is not None else None

    async def retry_failed(
        self, analysis_run_id: UUID, *, organization_id: UUID
    ) -> AnalysisRun | None:
        result = await self._session.execute(
            text(
                f"""
                UPDATE analysis_runs
                SET status = 'PROCESSING', processing_started_at = now(),
                    attempt_count = attempt_count + 1, error_message = NULL,
                    insufficient_evidence_reason = NULL, updated_at = now()
                WHERE id = :id AND organization_id = :organization_id AND status = 'FAILED'
                RETURNING {_RUN_COLUMNS}
                """
            ),
            {"id": analysis_run_id, "organization_id": organization_id},
        )
        row = result.mappings().first()
        await self._session.commit()
        return _run_from_row(row) if row is not None else None

    async def reclaim_stale(
        self, analysis_run_id: UUID, *, organization_id: UUID, stale_after_seconds: int
    ) -> AnalysisRun | None:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)
        result = await self._session.execute(
            text(
                f"""
                UPDATE analysis_runs
                SET processing_started_at = now(), attempt_count = attempt_count + 1,
                    updated_at = now()
                WHERE id = :id AND organization_id = :organization_id
                  AND status = 'PROCESSING' AND processing_started_at < :cutoff
                RETURNING {_RUN_COLUMNS}
                """
            ),
            {
                "id": analysis_run_id,
                "organization_id": organization_id,
                "cutoff": cutoff,
            },
        )
        row = result.mappings().first()
        await self._session.commit()
        return _run_from_row(row) if row is not None else None

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
        await self._session.execute(
            text(
                """
                UPDATE analysis_runs
                SET status = 'COMPLETED', structured_output = CAST(:structured_output AS jsonb),
                    error_message = NULL, prompt_tokens = :prompt_tokens,
                    completion_tokens = :completion_tokens, total_tokens = :total_tokens,
                    estimated_cost = :estimated_cost, completed_at = now(), updated_at = now()
                WHERE id = :id AND organization_id = :organization_id AND status = 'PROCESSING'
                """
            ),
            {
                "id": analysis_run_id,
                "organization_id": organization_id,
                "structured_output": json.dumps(structured_output),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "estimated_cost": estimated_cost,
            },
        )
        await self._session.commit()

    async def mark_failed(
        self, analysis_run_id: UUID, *, organization_id: UUID, error_message: str
    ) -> None:
        await self._session.execute(
            text(
                """
                UPDATE analysis_runs
                SET status = 'FAILED', error_message = :error_message, structured_output = NULL,
                    updated_at = now()
                WHERE id = :id AND organization_id = :organization_id AND status = 'PROCESSING'
                """
            ),
            {
                "id": analysis_run_id,
                "organization_id": organization_id,
                "error_message": error_message,
            },
        )
        await self._session.commit()

    async def mark_insufficient_evidence(
        self, analysis_run_id: UUID, *, organization_id: UUID, reason: str
    ) -> None:
        await self._session.execute(
            text(
                """
                UPDATE analysis_runs
                SET status = 'INSUFFICIENT_EVIDENCE', insufficient_evidence_reason = :reason,
                    structured_output = NULL, error_message = NULL, completed_at = now(),
                    updated_at = now()
                WHERE id = :id AND organization_id = :organization_id AND status = 'PROCESSING'
                """
            ),
            {
                "id": analysis_run_id,
                "organization_id": organization_id,
                "reason": reason,
            },
        )
        await self._session.commit()

    async def add_citations(
        self,
        analysis_run_id: UUID,
        *,
        organization_id: UUID,
        citations: Sequence[NewCitation],
    ) -> Sequence[AnalysisSourceReference]:
        if not citations:
            return []
        stmt = text(
            f"""
            INSERT INTO analysis_source_references
              (analysis_run_id, chunk_id, document_id, engagement_id, organization_id,
               chunk_index, char_start, char_end, quoted_snippet, citation_order, relevance_score)
            SELECT :analysis_run_id, dc.id, d.id, e.id, e.organization_id,
                   dc.chunk_index, :char_start, :char_end, :quoted_snippet, :citation_order,
                   :relevance_score
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            JOIN engagements e ON e.id = d.engagement_id
            WHERE dc.id = :chunk_id AND e.organization_id = :organization_id
            RETURNING {_CITATION_COLUMNS}
            """
        )
        inserted: list[AnalysisSourceReference] = []
        for citation in citations:
            result = await self._session.execute(
                stmt,
                {
                    "analysis_run_id": analysis_run_id,
                    "chunk_id": citation.chunk_id,
                    "organization_id": organization_id,
                    "char_start": citation.char_start,
                    "char_end": citation.char_end,
                    "quoted_snippet": citation.quoted_snippet,
                    "citation_order": citation.citation_order,
                    "relevance_score": citation.relevance_score,
                },
            )
            row = result.mappings().first()
            if row is not None:
                inserted.append(_citation_from_row(row))
        await self._session.commit()
        return inserted

    async def get_citations(
        self, analysis_run_id: UUID, *, organization_id: UUID
    ) -> Sequence[AnalysisSourceReference]:
        result = await self._session.execute(
            text(
                f"SELECT {_CITATION_COLUMNS} FROM analysis_source_references "
                "WHERE analysis_run_id = :analysis_run_id "
                "AND organization_id = :organization_id ORDER BY citation_order"
            ),
            {"analysis_run_id": analysis_run_id, "organization_id": organization_id},
        )
        return [_citation_from_row(row) for row in result.mappings().all()]

    async def delete(self, entity: AnalysisRun) -> None:
        if entity.id is None:
            return
        await self._session.execute(
            text("DELETE FROM analysis_runs WHERE id = :id"), {"id": entity.id}
        )
        await self._session.commit()
