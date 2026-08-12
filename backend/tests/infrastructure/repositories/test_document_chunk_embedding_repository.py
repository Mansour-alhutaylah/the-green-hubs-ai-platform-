"""Integration tests for ``SQLAlchemyDocumentChunkEmbeddingRepository``
against a real database (pgvector, migration ``3f3acc7fc556``).

Every row a test creates is tracked and deleted, via an independent
session, in ``cleanup_ids``'s teardown -- regardless of test outcome, in
dependency-safe order: document_chunk_embeddings, then document_chunks,
then documents, then engagements, then organizations.

Marked ``integration`` module-wide, mirroring
``test_processing_repositories.py``.
"""

import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, Callable, Awaitable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.db.models.document import DocumentModel
from app.infrastructure.db.models.document_chunk import DocumentChunkModel
from app.infrastructure.db.models.document_chunk_embedding import DocumentChunkEmbeddingModel
from app.infrastructure.db.models.engagement import Engagement as EngagementModel
from app.infrastructure.db.models.organization import Organization as OrganizationModel
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.repositories.document_chunk_embedding import (
    SQLAlchemyDocumentChunkEmbeddingRepository,
)

pytestmark = pytest.mark.integration

PROVIDER = "openai"
MODEL = "text-embedding-3-small"
MODEL_VERSION = ""
DIMENSION = 1536


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _vector(fill: float = 0.001) -> list[float]:
    return [fill] * DIMENSION


@pytest.fixture(autouse=True)
def _require_database_url() -> None:
    if not get_settings().database_url:
        pytest.skip("integration tests require DATABASE_URL to be set")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def cleanup_ids() -> AsyncIterator[dict[str, list[uuid.UUID]]]:
    ids: dict[str, list[uuid.UUID]] = {
        "embeddings": [], "chunks": [], "documents": [], "engagements": [], "organizations": [],
    }
    yield ids
    async with AsyncSessionLocal() as cleanup_session:
        for embedding_id in ids["embeddings"]:
            model = await cleanup_session.get(DocumentChunkEmbeddingModel, embedding_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for chunk_id in ids["chunks"]:
            model = await cleanup_session.get(DocumentChunkModel, chunk_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for document_id in ids["documents"]:
            model = await cleanup_session.get(DocumentModel, document_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for engagement_id in ids["engagements"]:
            model = await cleanup_session.get(EngagementModel, engagement_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for organization_id in ids["organizations"]:
            model = await cleanup_session.get(OrganizationModel, organization_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()


@pytest.fixture
def make_chunk(
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> Callable[..., Awaitable[tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, str]]]:
    """Factory: creates a real Organization + Engagement + Document
    (PROCESSED) + DocumentChunk row. Returns
    (chunk_id, document_id, engagement_id, organization_id, content)."""

    async def _make(content: str = "Emissions decreased year over year.") -> tuple:
        async with AsyncSessionLocal() as session:
            organization = OrganizationModel(name="Embedding Repo Test Org")
            session.add(organization)
            await session.flush()
            engagement = EngagementModel(
                organization_id=organization.id, title="Embedding Repo Test Engagement"
            )
            session.add(engagement)
            await session.flush()
            document = DocumentModel(
                filename="report.pdf", storage_path=f"test/{uuid.uuid4()}.pdf",
                processing_status="PROCESSED", engagement_id=engagement.id,
            )
            session.add(document)
            await session.flush()
            chunk = DocumentChunkModel(
                document_id=document.id, chunk_index=0, content=content,
                char_start=0, char_end=len(content),
            )
            session.add(chunk)
            await session.commit()
            await session.refresh(chunk)
        cleanup_ids["organizations"].append(organization.id)
        cleanup_ids["engagements"].append(engagement.id)
        cleanup_ids["documents"].append(document.id)
        cleanup_ids["chunks"].append(chunk.id)
        return chunk.id, document.id, engagement.id, organization.id, content

    return _make


@pytest.fixture
async def chunk(make_chunk) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, str]:
    return await make_chunk()


def _track(cleanup_ids: dict[str, list[uuid.UUID]], rows) -> None:
    cleanup_ids["embeddings"].extend(r.id for r in rows if r.id is not None)


# ---------------------------------------------------------------------------
# Lineage derivation
# ---------------------------------------------------------------------------


async def test_claim_new_derives_lineage_from_real_chunk_ownership(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], chunk
) -> None:
    chunk_id, document_id, engagement_id, organization_id, content = chunk
    repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)

    claimed = await repository.claim_new(
        [chunk_id], organization_id=organization_id, provider=PROVIDER, model=MODEL, model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, content_hashes={chunk_id: _content_hash(content)},
    )
    _track(cleanup_ids, claimed)

    assert len(claimed) == 1
    row = claimed[0]
    assert row.document_id == document_id
    assert row.engagement_id == engagement_id
    assert row.organization_id == organization_id
    assert row.status == "PROCESSING"
    assert row.embedding is None


async def test_composite_foreign_key_rejects_mismatched_organization(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], chunk, make_chunk
) -> None:
    """Declarative backstop: even a raw INSERT that bypasses the
    repository's derived lineage cannot claim a foreign organization_id
    for a real chunk_id/document_id/engagement_id."""
    chunk_id, document_id, engagement_id, _organization_id, content = chunk
    _other_chunk_id, _od, _oe, other_organization_id, _oc = await make_chunk("Unrelated content.")

    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await session.execute(
            text(
                """
                INSERT INTO document_chunk_embeddings
                  (chunk_id, document_id, engagement_id, organization_id,
                   provider, model, model_version, embedding_dimension, content_hash, status)
                VALUES (:chunk_id, :document_id, :engagement_id, :organization_id,
                        :provider, :model, :model_version, :dimension, :content_hash, 'PROCESSING')
                """
            ),
            {
                "chunk_id": chunk_id, "document_id": document_id, "engagement_id": engagement_id,
                "organization_id": other_organization_id, "provider": PROVIDER, "model": MODEL,
                "model_version": MODEL_VERSION, "dimension": DIMENSION,
                "content_hash": _content_hash(content),
            },
        )
    await session.rollback()


# ---------------------------------------------------------------------------
# Duplicate prevention / identity uniqueness
# ---------------------------------------------------------------------------


async def test_claim_new_is_idempotent_via_on_conflict_do_nothing(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], chunk
) -> None:
    chunk_id, _d, _e, organization_id, content = chunk
    repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)
    hashes = {chunk_id: _content_hash(content)}

    first = await repository.claim_new(
        [chunk_id], organization_id=organization_id, provider=PROVIDER, model=MODEL, model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, content_hashes=hashes,
    )
    _track(cleanup_ids, first)
    second = await repository.claim_new(
        [chunk_id], organization_id=organization_id, provider=PROVIDER, model=MODEL, model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, content_hashes=hashes,
    )

    assert len(first) == 1
    assert len(second) == 0  # already exists, silently excluded


async def test_two_concurrent_first_claims_only_one_wins(
    cleanup_ids: dict[str, list[uuid.UUID]], chunk
) -> None:
    chunk_id, _d, _e, organization_id, content = chunk
    hashes = {chunk_id: _content_hash(content)}

    async def _attempt() -> int:
        async with AsyncSessionLocal() as session:
            repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)
            claimed = await repository.claim_new(
                [chunk_id], organization_id=organization_id, provider=PROVIDER, model=MODEL, model_version=MODEL_VERSION,
                embedding_dimension=DIMENSION, content_hashes=hashes,
            )
            return len(claimed)

    results = await asyncio.gather(_attempt(), _attempt())

    assert sorted(results) == [0, 1]  # exactly one winner

    async with AsyncSessionLocal() as verify_session:
        from sqlalchemy import select

        result = await verify_session.execute(
            select(DocumentChunkEmbeddingModel).where(
                DocumentChunkEmbeddingModel.chunk_id == chunk_id
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 1  # never duplicated
        cleanup_ids["embeddings"].append(rows[0].id)


# ---------------------------------------------------------------------------
# FAILED retry
# ---------------------------------------------------------------------------


async def test_retry_failed_transitions_and_increments_attempt_count(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], chunk
) -> None:
    chunk_id, _d, _e, organization_id, content = chunk
    repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)
    claimed = await repository.claim_new(
        [chunk_id], organization_id=organization_id, provider=PROVIDER, model=MODEL, model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, content_hashes={chunk_id: _content_hash(content)},
    )
    _track(cleanup_ids, claimed)
    row = claimed[0]
    await repository.mark_failed([row.id], organization_id=organization_id, error_message="Embedding provider unavailable")

    retried = await repository.retry_failed([row.id], organization_id=organization_id)

    assert len(retried) == 1
    assert retried[0].status == "PROCESSING"
    assert retried[0].attempt_count == 2
    assert retried[0].error_message is None
    assert retried[0].updated_at > row.updated_at


async def test_retry_failed_does_not_touch_non_failed_rows(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], chunk
) -> None:
    chunk_id, _d, _e, organization_id, content = chunk
    repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)
    claimed = await repository.claim_new(
        [chunk_id], organization_id=organization_id, provider=PROVIDER, model=MODEL, model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, content_hashes={chunk_id: _content_hash(content)},
    )
    _track(cleanup_ids, claimed)
    row = claimed[0]  # still PROCESSING, not FAILED

    retried = await repository.retry_failed([row.id], organization_id=organization_id)

    assert retried == []


# ---------------------------------------------------------------------------
# Stale reclaim
# ---------------------------------------------------------------------------


async def test_non_stale_processing_row_cannot_be_reclaimed(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], chunk
) -> None:
    chunk_id, _d, _e, organization_id, content = chunk
    repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)
    claimed = await repository.claim_new(
        [chunk_id], organization_id=organization_id, provider=PROVIDER, model=MODEL, model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, content_hashes={chunk_id: _content_hash(content)},
    )
    _track(cleanup_ids, claimed)
    row = claimed[0]  # processing_started_at = now(), not stale

    reclaimed = await repository.reclaim_stale([row.id], organization_id=organization_id, stale_after_seconds=300)

    assert reclaimed == []


async def test_stale_processing_row_can_be_reclaimed_exactly_once(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], chunk
) -> None:
    chunk_id, _d, _e, organization_id, content = chunk
    repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)
    claimed = await repository.claim_new(
        [chunk_id], organization_id=organization_id, provider=PROVIDER, model=MODEL, model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, content_hashes={chunk_id: _content_hash(content)},
    )
    _track(cleanup_ids, claimed)
    row = claimed[0]

    from sqlalchemy import text

    stale_time = datetime.now(timezone.utc) - timedelta(seconds=999)
    await session.execute(
        text("UPDATE document_chunk_embeddings SET processing_started_at = :t WHERE id = :id"),
        {"t": stale_time, "id": row.id},
    )
    await session.commit()

    first_reclaim = await repository.reclaim_stale([row.id], organization_id=organization_id, stale_after_seconds=300)
    second_reclaim = await repository.reclaim_stale([row.id], organization_id=organization_id, stale_after_seconds=300)

    assert len(first_reclaim) == 1
    assert first_reclaim[0].attempt_count == 2
    assert second_reclaim == []  # no longer stale immediately after reclaim


async def test_two_concurrent_stale_reclaim_attempts_only_one_wins(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], chunk
) -> None:
    chunk_id, _d, _e, organization_id, content = chunk
    repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)
    claimed = await repository.claim_new(
        [chunk_id], organization_id=organization_id, provider=PROVIDER, model=MODEL, model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, content_hashes={chunk_id: _content_hash(content)},
    )
    _track(cleanup_ids, claimed)
    row = claimed[0]

    from sqlalchemy import text

    stale_time = datetime.now(timezone.utc) - timedelta(seconds=999)
    await session.execute(
        text("UPDATE document_chunk_embeddings SET processing_started_at = :t WHERE id = :id"),
        {"t": stale_time, "id": row.id},
    )
    await session.commit()

    async def _attempt() -> int:
        async with AsyncSessionLocal() as reclaim_session:
            reclaim_repository = SQLAlchemyDocumentChunkEmbeddingRepository(reclaim_session)
            reclaimed = await reclaim_repository.reclaim_stale([row.id], organization_id=organization_id, stale_after_seconds=300)
            return len(reclaimed)

    results = await asyncio.gather(_attempt(), _attempt())

    assert sorted(results) == [0, 1]


# ---------------------------------------------------------------------------
# Batch resolution + updated_at
# ---------------------------------------------------------------------------


async def test_mark_completed_persists_vector_and_updates_timestamp(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], chunk
) -> None:
    chunk_id, _d, _e, organization_id, content = chunk
    repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)
    claimed = await repository.claim_new(
        [chunk_id], organization_id=organization_id, provider=PROVIDER, model=MODEL, model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, content_hashes={chunk_id: _content_hash(content)},
    )
    _track(cleanup_ids, claimed)
    row = claimed[0]

    await repository.mark_completed([(row.id, _vector(0.5))], organization_id=organization_id)

    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(DocumentChunkEmbeddingModel, row.id)
        assert model is not None
        assert model.status == "COMPLETED"
        assert model.embedding is not None
        assert len(model.embedding) == DIMENSION
        assert model.updated_at > row.updated_at


async def test_mark_failed_persists_sanitized_message(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], chunk
) -> None:
    chunk_id, _d, _e, organization_id, content = chunk
    repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)
    claimed = await repository.claim_new(
        [chunk_id], organization_id=organization_id, provider=PROVIDER, model=MODEL, model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, content_hashes={chunk_id: _content_hash(content)},
    )
    _track(cleanup_ids, claimed)
    row = claimed[0]

    await repository.mark_failed([row.id], organization_id=organization_id, error_message="Embedding provider unavailable")

    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(DocumentChunkEmbeddingModel, row.id)
        assert model is not None
        assert model.status == "FAILED"
        assert model.embedding is None
        assert model.error_message == "Embedding provider unavailable"


# ---------------------------------------------------------------------------
# Tenant-safe similarity search
# ---------------------------------------------------------------------------


async def test_search_returns_only_same_tenant_results_ordered_by_similarity(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], make_chunk
) -> None:
    chunk_a_id, document_id, engagement_a, organization_a, content_a = await make_chunk(
        "Close match content."
    )
    # A second chunk under the *same* document/tenant -- not a second
    # make_chunk() call, which would create an unrelated organization.
    content_far = "Unrelated far content."
    async with AsyncSessionLocal() as second_session:
        far_chunk = DocumentChunkModel(
            document_id=document_id, chunk_index=1, content=content_far,
            char_start=0, char_end=len(content_far),
        )
        second_session.add(far_chunk)
        await second_session.commit()
        await second_session.refresh(far_chunk)
    chunk_far_id = far_chunk.id
    cleanup_ids["chunks"].append(chunk_far_id)

    repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)
    claimed_a = await repository.claim_new(
        [chunk_a_id], organization_id=organization_a, provider=PROVIDER, model=MODEL,
        model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, content_hashes={chunk_a_id: _content_hash(content_a)},
    )
    claimed_far = await repository.claim_new(
        [chunk_far_id], organization_id=organization_a, provider=PROVIDER, model=MODEL,
        model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, content_hashes={chunk_far_id: _content_hash(content_far)},
    )
    _track(cleanup_ids, claimed_a)
    _track(cleanup_ids, claimed_far)
    await repository.mark_completed(
        [(claimed_a[0].id, _vector(0.9))], organization_id=organization_a
    )
    await repository.mark_completed(
        [(claimed_far[0].id, _vector(-0.1))], organization_id=organization_a
    )

    results = await repository.search(
        organization_id=organization_a, provider=PROVIDER, model=MODEL,
        model_version=MODEL_VERSION, query_vector=_vector(0.9), top_k=10,
    )

    result_chunk_ids = [r.chunk_id for r in results]
    assert chunk_a_id in result_chunk_ids
    assert chunk_far_id in result_chunk_ids
    assert result_chunk_ids[0] == chunk_a_id  # closer match ranks first


async def test_cross_tenant_nearest_neighbor_is_never_returned(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], make_chunk
) -> None:
    """Two organizations, deliberately near-identical embedded content --
    proves Organization B's closer-by-similarity chunk is never returned
    to an Organization A search, even though it would rank first by raw
    distance alone."""
    chunk_a_id, _da, _ea, organization_a, content_a = await make_chunk(
        "Scope 1 emissions data for fiscal year."
    )
    chunk_b_id, _db, _eb, organization_b, content_b = await make_chunk(
        "Scope 1 emissions data for fiscal year."  # intentionally identical content
    )

    repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)
    # Each chunk is claimed under its *own* organization -- the derived
    # lineage and the supplied scope agree, which is the only way a claim
    # succeeds now.
    claimed_a = await repository.claim_new(
        [chunk_a_id], organization_id=organization_a, provider=PROVIDER, model=MODEL,
        model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, content_hashes={chunk_a_id: _content_hash(content_a)},
    )
    claimed_b = await repository.claim_new(
        [chunk_b_id], organization_id=organization_b, provider=PROVIDER, model=MODEL,
        model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, content_hashes={chunk_b_id: _content_hash(content_b)},
    )
    _track(cleanup_ids, claimed_a)
    _track(cleanup_ids, claimed_b)

    # MVP Slice 3: claiming B's chunk under A's scope inserts nothing at
    # all -- the derived-lineage join now also constrains on organization.
    assert await repository.claim_new(
        [chunk_b_id], organization_id=organization_a, provider=PROVIDER, model=MODEL,
        model_version="cross-tenant-probe",
        embedding_dimension=DIMENSION, content_hashes={chunk_b_id: _content_hash(content_b)},
    ) == []

    query_vector = _vector(0.777)
    # Both get the *exact same* vector -- B would be an equally-perfect
    # match for an A-scoped query if tenant scope were not enforced.
    await repository.mark_completed(
        [(claimed_a[0].id, query_vector)], organization_id=organization_a
    )
    await repository.mark_completed(
        [(claimed_b[0].id, query_vector)], organization_id=organization_b
    )

    # A cross-tenant write is equally inert: A cannot resolve B's row.
    await repository.mark_failed(
        [claimed_b[0].id], organization_id=organization_a, error_message="cross-tenant write"
    )

    results = await repository.search(
        organization_id=organization_a, provider=PROVIDER, model=MODEL,
        model_version=MODEL_VERSION, query_vector=query_vector, top_k=10,
    )

    result_chunk_ids = {r.chunk_id for r in results}
    assert chunk_a_id in result_chunk_ids
    assert chunk_b_id not in result_chunk_ids
    assert all(r.similarity_score >= 0 for r in results)

    other_results = await repository.search(
        organization_id=organization_b, provider=PROVIDER, model=MODEL,
        model_version=MODEL_VERSION, query_vector=query_vector, top_k=10,
    )
    # B still sees its own row COMPLETED -- A's cross-tenant mark_failed
    # above changed nothing.
    assert {r.chunk_id for r in other_results} == {chunk_b_id}


async def test_search_excludes_non_completed_rows(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], chunk
) -> None:
    chunk_id, _d, _e, organization_id, content = chunk
    repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)
    claimed = await repository.claim_new(
        [chunk_id], organization_id=organization_id, provider=PROVIDER, model=MODEL, model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, content_hashes={chunk_id: _content_hash(content)},
    )
    _track(cleanup_ids, claimed)  # left PROCESSING -- never resolved

    results = await repository.search(
        organization_id=organization_id, provider=PROVIDER, model=MODEL,
        model_version=MODEL_VERSION, query_vector=_vector(), top_k=10,
    )

    assert results == []


async def test_search_filters_by_engagement_id(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], chunk
) -> None:
    chunk_id, _d, engagement_id, organization_id, content = chunk
    repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)
    claimed = await repository.claim_new(
        [chunk_id], organization_id=organization_id, provider=PROVIDER, model=MODEL, model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, content_hashes={chunk_id: _content_hash(content)},
    )
    _track(cleanup_ids, claimed)
    await repository.mark_completed(
        [(claimed[0].id, _vector())], organization_id=organization_id
    )

    matching_results = await repository.search(
        organization_id=organization_id, provider=PROVIDER, model=MODEL,
        model_version=MODEL_VERSION, query_vector=_vector(), top_k=10, engagement_id=engagement_id,
    )
    assert {r.chunk_id for r in matching_results} == {chunk_id}

    unrelated_engagement_results = await repository.search(
        organization_id=organization_id, provider=PROVIDER, model=MODEL,
        model_version=MODEL_VERSION, query_vector=_vector(), top_k=10,
        engagement_id=uuid.uuid4(),
    )
    assert unrelated_engagement_results == []


async def test_search_filters_by_document_id(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], make_chunk
) -> None:
    chunk_a_id, document_a, _ea, organization_id, content_a = await make_chunk("Document A content.")
    chunk_b_id, document_b, _eb, _ob, content_b = await make_chunk("Document B content.")

    repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)
    claimed_a = await repository.claim_new(
        [chunk_a_id], organization_id=organization_id, provider=PROVIDER, model=MODEL, model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, content_hashes={chunk_a_id: _content_hash(content_a)},
    )
    _track(cleanup_ids, claimed_a)
    await repository.mark_completed(
        [(claimed_a[0].id, _vector())], organization_id=organization_id
    )

    results = await repository.search(
        organization_id=organization_id, provider=PROVIDER, model=MODEL,
        model_version=MODEL_VERSION, query_vector=_vector(), top_k=10, document_id=document_a,
    )
    assert {r.chunk_id for r in results} == {chunk_a_id}

    empty_results = await repository.search(
        organization_id=organization_id, provider=PROVIDER, model=MODEL,
        model_version=MODEL_VERSION, query_vector=_vector(), top_k=10, document_id=document_b,
    )
    assert empty_results == []


async def test_search_filters_by_provider_model_version_identity(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], chunk
) -> None:
    chunk_id, _d, _e, organization_id, content = chunk
    repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)
    claimed = await repository.claim_new(
        [chunk_id], organization_id=organization_id, provider=PROVIDER, model=MODEL, model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, content_hashes={chunk_id: _content_hash(content)},
    )
    _track(cleanup_ids, claimed)
    await repository.mark_completed(
        [(claimed[0].id, _vector())], organization_id=organization_id
    )

    wrong_model_results = await repository.search(
        organization_id=organization_id, provider=PROVIDER, model="a-different-model",
        model_version=MODEL_VERSION, query_vector=_vector(), top_k=10,
    )
    assert wrong_model_results == []

    correct_results = await repository.search(
        organization_id=organization_id, provider=PROVIDER, model=MODEL,
        model_version=MODEL_VERSION, query_vector=_vector(), top_k=10,
    )
    assert len(correct_results) == 1
