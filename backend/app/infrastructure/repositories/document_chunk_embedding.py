"""Concrete async repository for the ``DocumentChunkEmbedding`` aggregate.

Sprint 3.6A, Vector Retrieval Foundation. Every write method commits
immediately (never just flushes) -- these are atomic concurrency facts
other requests must observe right away, mirroring
``SQLAlchemyDocumentRepository.begin_processing()``'s rationale exactly.

Raw ``text()`` SQL is used throughout rather than the ORM query builder:
this repository's defining property is that tenant lineage
(document_id/engagement_id/organization_id) must be *derived* by the
database from ``chunk_id``'s real ownership chain, never accepted as an
application-supplied value -- an ``INSERT ... SELECT ... JOIN`` shape
that is more directly and auditably expressed as explicit SQL than
coaxed out of the ORM-enabled bulk-insert API, which is built for plain
VALUES inserts, not INSERT-from-SELECT-with-JOIN.

MVP Slice 3 (Organization Data Isolation): every statement in this class
now also carries ``organization_id = :organization_id`` (or, for
``claim_new``, ``e.organization_id = :organization_id`` on the derived
lineage). ``search`` already did; the state-transition methods did not,
and located rows by bare embedding id alone. These rows hold the vectors
retrieval ranks over, so an unscoped write here could have corrupted or
resurrected another tenant's embeddings, and an unscoped read could have
fed them into a ranking. Tenant filtering is in the query for every one
of them -- never applied to candidates after retrieval.
"""

from datetime import datetime, timedelta, timezone
from typing import Mapping, Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.document_chunk_embedding import DocumentChunkEmbedding
from app.domain.entities.vector_search_result import VectorSearchResult
from app.domain.repositories.document_chunk_embedding import IDocumentChunkEmbeddingRepository

_COLUMNS = (
    "id, chunk_id, document_id, engagement_id, organization_id, provider, model, "
    "model_version, embedding_dimension, embedding, content_hash, status, "
    "error_message, processing_started_at, attempt_count, created_at, updated_at"
)


def _row_to_domain(row) -> DocumentChunkEmbedding:
    return DocumentChunkEmbedding(
        id=row.id,
        chunk_id=row.chunk_id,
        document_id=row.document_id,
        engagement_id=row.engagement_id,
        organization_id=row.organization_id,
        provider=row.provider,
        model=row.model,
        model_version=row.model_version,
        embedding_dimension=row.embedding_dimension,
        embedding=list(row.embedding) if row.embedding is not None else None,
        content_hash=row.content_hash,
        status=row.status,
        error_message=row.error_message,
        processing_started_at=row.processing_started_at,
        attempt_count=row.attempt_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


class SQLAlchemyDocumentChunkEmbeddingRepository(IDocumentChunkEmbeddingRepository):
    """Async, PostgreSQL/pgvector-backed implementation of
    ``IDocumentChunkEmbeddingRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
        if not chunk_ids:
            return []
        claimed: list[DocumentChunkEmbedding] = []
        # `e.organization_id` is still the value written to the new row --
        # derived from the chunk's real lineage, never from the caller.
        # `= :organization_id` is a separate, additional constraint on
        # which chunks may be claimed at all, so a foreign chunk_id
        # inserts nothing rather than claiming another tenant's chunk.
        stmt = text(
            f"""
            INSERT INTO document_chunk_embeddings
              (chunk_id, document_id, engagement_id, organization_id,
               provider, model, model_version, embedding_dimension, content_hash, status)
            SELECT dc.id, d.id, e.id, e.organization_id,
                   :provider, :model, :model_version, :dimension, :content_hash, 'PROCESSING'
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            JOIN engagements e ON e.id = d.engagement_id
            WHERE dc.id = :chunk_id AND e.organization_id = :organization_id
            ON CONFLICT (chunk_id, provider, model, model_version) DO NOTHING
            RETURNING {_COLUMNS}
            """
        )
        for chunk_id in chunk_ids:
            result = await self._session.execute(
                stmt,
                {
                    "chunk_id": chunk_id,
                    "organization_id": organization_id,
                    "provider": provider,
                    "model": model,
                    "model_version": model_version,
                    "dimension": embedding_dimension,
                    "content_hash": content_hashes[chunk_id],
                },
            )
            row = result.mappings().first()
            if row is not None:
                claimed.append(_row_to_domain(row))
        await self._session.commit()
        return claimed

    async def get_existing(
        self,
        chunk_ids: Sequence[UUID],
        *,
        organization_id: UUID,
        provider: str,
        model: str,
        model_version: str,
    ) -> Sequence[DocumentChunkEmbedding]:
        if not chunk_ids:
            return []
        result = await self._session.execute(
            text(
                f"""
                SELECT {_COLUMNS} FROM document_chunk_embeddings
                WHERE chunk_id = ANY(:chunk_ids) AND organization_id = :organization_id
                  AND provider = :provider
                  AND model = :model AND model_version = :model_version
                """
            ),
            {
                "chunk_ids": list(chunk_ids),
                "organization_id": organization_id,
                "provider": provider,
                "model": model,
                "model_version": model_version,
            },
        )
        return [_row_to_domain(row) for row in result.mappings().all()]

    async def retry_failed(
        self, embedding_ids: Sequence[UUID], *, organization_id: UUID
    ) -> Sequence[DocumentChunkEmbedding]:
        if not embedding_ids:
            return []
        result = await self._session.execute(
            text(
                f"""
                UPDATE document_chunk_embeddings
                SET status = 'PROCESSING', processing_started_at = now(),
                    attempt_count = attempt_count + 1, error_message = NULL, updated_at = now()
                WHERE id = ANY(:ids) AND organization_id = :organization_id
                  AND status = 'FAILED'
                RETURNING {_COLUMNS}
                """
            ),
            {"ids": list(embedding_ids), "organization_id": organization_id},
        )
        rows = result.mappings().all()
        await self._session.commit()
        return [_row_to_domain(row) for row in rows]

    async def reclaim_stale(
        self,
        embedding_ids: Sequence[UUID],
        *,
        organization_id: UUID,
        stale_after_seconds: int,
    ) -> Sequence[DocumentChunkEmbedding]:
        if not embedding_ids:
            return []
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)
        result = await self._session.execute(
            text(
                f"""
                UPDATE document_chunk_embeddings
                SET processing_started_at = now(), attempt_count = attempt_count + 1,
                    error_message = NULL, updated_at = now()
                WHERE id = ANY(:ids) AND organization_id = :organization_id
                  AND status = 'PROCESSING' AND processing_started_at < :cutoff
                RETURNING {_COLUMNS}
                """
            ),
            {
                "ids": list(embedding_ids),
                "organization_id": organization_id,
                "cutoff": cutoff,
            },
        )
        rows = result.mappings().all()
        await self._session.commit()
        return [_row_to_domain(row) for row in rows]

    async def mark_completed(
        self, results: Sequence[tuple[UUID, Sequence[float]]], *, organization_id: UUID
    ) -> None:
        if not results:
            return
        stmt = text(
            """
            UPDATE document_chunk_embeddings
            SET status = 'COMPLETED', embedding = :embedding, error_message = NULL,
                updated_at = now()
            WHERE id = :id AND organization_id = :organization_id
            """
        )
        for embedding_id, vector in results:
            await self._session.execute(
                stmt,
                {
                    "id": embedding_id,
                    "organization_id": organization_id,
                    "embedding": _vector_literal(vector),
                },
            )
        await self._session.commit()

    async def mark_failed(
        self, embedding_ids: Sequence[UUID], *, organization_id: UUID, error_message: str
    ) -> None:
        if not embedding_ids:
            return
        await self._session.execute(
            text(
                """
                UPDATE document_chunk_embeddings
                SET status = 'FAILED', error_message = :error_message, updated_at = now()
                WHERE id = ANY(:ids) AND organization_id = :organization_id
                """
            ),
            {
                "ids": list(embedding_ids),
                "organization_id": organization_id,
                "error_message": error_message,
            },
        )
        await self._session.commit()

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
        result = await self._session.execute(
            text(
                """
                SELECT dc.chunk_index, dc.content, dc.char_start, dc.char_end,
                       dce.chunk_id, dce.document_id, dce.engagement_id,
                       1 - (dce.embedding <=> :query_vector) AS similarity_score
                FROM document_chunk_embeddings dce
                JOIN document_chunks dc ON dc.id = dce.chunk_id
                WHERE dce.organization_id = :organization_id
                  AND dce.status = 'COMPLETED'
                  AND dce.provider = :provider
                  AND dce.model = :model
                  AND dce.model_version = :model_version
                  AND (CAST(:engagement_id AS uuid) IS NULL
                       OR dce.engagement_id = CAST(:engagement_id AS uuid))
                  AND (CAST(:document_id AS uuid) IS NULL
                       OR dce.document_id = CAST(:document_id AS uuid))
                ORDER BY dce.embedding <=> :query_vector
                LIMIT :top_k
                """
            ),
            {
                "organization_id": organization_id,
                "provider": provider,
                "model": model,
                "model_version": model_version,
                "query_vector": _vector_literal(query_vector),
                "engagement_id": engagement_id,
                "document_id": document_id,
                "top_k": top_k,
            },
        )
        return [
            VectorSearchResult(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                engagement_id=row.engagement_id,
                chunk_index=row.chunk_index,
                content=row.content,
                char_start=row.char_start,
                char_end=row.char_end,
                similarity_score=float(row.similarity_score),
            )
            for row in result.mappings().all()
        ]

    async def delete(self, entity: DocumentChunkEmbedding) -> None:
        if entity.id is None:
            return
        await self._session.execute(
            text("DELETE FROM document_chunk_embeddings WHERE id = :id"), {"id": entity.id}
        )
        await self._session.commit()
