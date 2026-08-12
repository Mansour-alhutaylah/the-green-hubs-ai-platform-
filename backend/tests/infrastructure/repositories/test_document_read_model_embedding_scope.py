"""Integration tests for the embedding-identity scoping in
``SQLAlchemyDocumentRepository.get_read_model_for_organization`` /
``list_read_models_for_organization`` against a real database.

Regression coverage for a real production bug: a document previously
embedded under one (provider, model, model_version) identity, then
re-embedded under a different one after an OpenRouter migration changed
``EMBEDDING_MODEL`` from ``"text-embedding-3-small"`` to
``"openai/text-embedding-3-small"``. ``uq_document_chunk_embeddings_identity``
is unique per (chunk_id, provider, model, model_version), so the old
identity's rows are never overwritten or deleted -- they are real attempt
history. The document read-model's ``embedding_summary`` must reflect only the app's
*current* embedding identity, never a sum across every identity a
document happens to carry rows under.

Marked ``integration`` module-wide, mirroring
``test_document_chunk_embedding_repository.py``.
"""

import hashlib
import uuid
from typing import AsyncIterator, Awaitable, Callable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.db.models.document import DocumentModel
from app.infrastructure.db.models.document_chunk import DocumentChunkModel
from app.infrastructure.db.models.document_chunk_embedding import DocumentChunkEmbeddingModel
from app.infrastructure.db.models.engagement import Engagement as EngagementModel
from app.infrastructure.db.models.organization import Organization as OrganizationModel
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.repositories.document import SQLAlchemyDocumentRepository
from app.infrastructure.repositories.document_chunk_embedding import (
    SQLAlchemyDocumentChunkEmbeddingRepository,
)

pytestmark = pytest.mark.integration

PROVIDER = "openai"
OLD_MODEL = "text-embedding-3-small"
CURRENT_MODEL = "openai/text-embedding-3-small"
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
def make_document_with_chunks(
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> Callable[[int], Awaitable[tuple[uuid.UUID, uuid.UUID, uuid.UUID, list[uuid.UUID]]]]:
    """Factory: one real Organization + Engagement + PROCESSED Document,
    with ``count`` real DocumentChunk rows attached -- so multi-chunk
    aggregation is exercised against one real document, not one chunk
    per document like ``test_document_chunk_embedding_repository.py``'s
    own ``make_chunk``. Returns
    (document_id, engagement_id, organization_id, [chunk_id, ...])."""

    async def _make(count: int = 1) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, list[uuid.UUID]]:
        async with AsyncSessionLocal() as session:
            organization = OrganizationModel(name="Read Model Embedding Scope Test Org")
            session.add(organization)
            await session.flush()
            engagement = EngagementModel(
                organization_id=organization.id, title="Read Model Embedding Scope Test Engagement"
            )
            session.add(engagement)
            await session.flush()
            document = DocumentModel(
                filename="report.pdf",
                storage_path=f"test/{uuid.uuid4()}.pdf",
                processing_status="PROCESSED",
                engagement_id=engagement.id,
            )
            session.add(document)
            await session.flush()
            chunks = []
            for index in range(count):
                content = f"Chunk {index}: emissions decreased year over year."
                chunk = DocumentChunkModel(
                    document_id=document.id, chunk_index=index, content=content,
                    char_start=0, char_end=len(content),
                )
                session.add(chunk)
                chunks.append(chunk)
            await session.commit()
            for chunk in chunks:
                await session.refresh(chunk)
        cleanup_ids["organizations"].append(organization.id)
        cleanup_ids["engagements"].append(engagement.id)
        cleanup_ids["documents"].append(document.id)
        cleanup_ids["chunks"].extend(chunk.id for chunk in chunks)
        return document.id, engagement.id, organization.id, [chunk.id for chunk in chunks]

    return _make


def _track(cleanup_ids: dict[str, list[uuid.UUID]], rows) -> None:
    cleanup_ids["embeddings"].extend(r.id for r in rows if r.id is not None)


async def _fail_under_identity(
    repository: SQLAlchemyDocumentChunkEmbeddingRepository,
    cleanup_ids: dict[str, list[uuid.UUID]],
    chunk_ids: list[uuid.UUID],
    contents: list[str],
    *,
    organization_id: uuid.UUID,
    model: str,
) -> None:
    claimed = await repository.claim_new(
        chunk_ids,
        organization_id=organization_id,
        provider=PROVIDER,
        model=model,
        model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION,
        content_hashes={cid: _content_hash(c) for cid, c in zip(chunk_ids, contents)},
    )
    _track(cleanup_ids, claimed)
    await repository.mark_failed(
        [row.id for row in claimed if row.id is not None],
        organization_id=organization_id,
        error_message="Embedding provider rejected the request",
    )


async def _complete_under_identity(
    repository: SQLAlchemyDocumentChunkEmbeddingRepository,
    cleanup_ids: dict[str, list[uuid.UUID]],
    chunk_ids: list[uuid.UUID],
    contents: list[str],
    *,
    organization_id: uuid.UUID,
    model: str,
) -> None:
    claimed = await repository.claim_new(
        chunk_ids,
        organization_id=organization_id,
        provider=PROVIDER,
        model=model,
        model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION,
        content_hashes={cid: _content_hash(c) for cid, c in zip(chunk_ids, contents)},
    )
    _track(cleanup_ids, claimed)
    await repository.mark_completed(
        [(row.id, _vector()) for row in claimed if row.id is not None],
        organization_id=organization_id,
    )


# ---------------------------------------------------------------------------
# The reported bug: a failed attempt under an old identity, then a
# successful retry under a new (current) identity.
# ---------------------------------------------------------------------------


async def test_stale_failed_attempt_under_old_identity_is_excluded_from_current_summary(
    session: AsyncSession,
    cleanup_ids: dict[str, list[uuid.UUID]],
    make_document_with_chunks,
) -> None:
    document_id, _engagement_id, organization_id, chunk_ids = await make_document_with_chunks(1)
    contents = ["Chunk 0: emissions decreased year over year."]
    embedding_repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)

    await _fail_under_identity(
        embedding_repository, cleanup_ids, chunk_ids, contents,
        organization_id=organization_id, model=OLD_MODEL
    )
    await _complete_under_identity(
        embedding_repository, cleanup_ids, chunk_ids, contents,
        organization_id=organization_id, model=CURRENT_MODEL
    )

    document_repository = SQLAlchemyDocumentRepository(session)
    read_model = await document_repository.get_read_model_for_organization(
        document_id,
        organization_id=organization_id,
        embedding_provider=PROVIDER,
        embedding_model=CURRENT_MODEL,
        embedding_model_version=MODEL_VERSION,
    )

    assert read_model is not None
    summary = read_model.embedding_summary
    assert summary.total_chunks == 1
    assert summary.completed == 1
    assert summary.failed == 0
    assert summary.processing == 0
    assert summary.is_complete is True


async def test_old_identity_still_shows_its_own_failed_history_when_queried_directly(
    session: AsyncSession,
    cleanup_ids: dict[str, list[uuid.UUID]],
    make_document_with_chunks,
) -> None:
    """Companion to the test above: proves the old row was never deleted
    or overwritten, only excluded from the *current* identity's summary
    -- attempt history is preserved, per the schema's own design."""
    document_id, _engagement_id, organization_id, chunk_ids = await make_document_with_chunks(1)
    contents = ["Chunk 0: emissions decreased year over year."]
    embedding_repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)

    await _fail_under_identity(
        embedding_repository, cleanup_ids, chunk_ids, contents,
        organization_id=organization_id, model=OLD_MODEL
    )
    await _complete_under_identity(
        embedding_repository, cleanup_ids, chunk_ids, contents,
        organization_id=organization_id, model=CURRENT_MODEL
    )

    document_repository = SQLAlchemyDocumentRepository(session)
    read_model = await document_repository.get_read_model_for_organization(
        document_id,
        organization_id=organization_id,
        embedding_provider=PROVIDER,
        embedding_model=OLD_MODEL,
        embedding_model_version=MODEL_VERSION,
    )

    assert read_model is not None
    summary = read_model.embedding_summary
    assert summary.total_chunks == 1
    assert summary.completed == 0
    assert summary.failed == 1


# ---------------------------------------------------------------------------
# No double-counting of historical attempts across multiple chunks.
# ---------------------------------------------------------------------------


async def test_multi_chunk_document_is_not_double_counted_across_identities(
    session: AsyncSession,
    cleanup_ids: dict[str, list[uuid.UUID]],
    make_document_with_chunks,
) -> None:
    document_id, _engagement_id, organization_id, chunk_ids = await make_document_with_chunks(4)
    contents = [f"Chunk {i}: emissions decreased year over year." for i in range(4)]
    embedding_repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)

    # Every chunk has a stale FAILED row under the old identity...
    await _fail_under_identity(
        embedding_repository, cleanup_ids, chunk_ids, contents,
        organization_id=organization_id, model=OLD_MODEL
    )
    # ...and a real, current-identity COMPLETED row -- 8 rows total for 4
    # chunks, exactly the shape that produced "4/8" in the UI bug report.
    await _complete_under_identity(
        embedding_repository, cleanup_ids, chunk_ids, contents,
        organization_id=organization_id, model=CURRENT_MODEL
    )

    document_repository = SQLAlchemyDocumentRepository(session)
    read_model = await document_repository.get_read_model_for_organization(
        document_id,
        organization_id=organization_id,
        embedding_provider=PROVIDER,
        embedding_model=CURRENT_MODEL,
        embedding_model_version=MODEL_VERSION,
    )

    assert read_model is not None
    assert read_model.chunk_count == 4
    summary = read_model.embedding_summary
    assert summary.total_chunks == 4  # not 8 -- one row per unique chunk, not per attempt
    assert summary.completed == 4
    assert summary.failed == 0
    assert summary.is_complete is True


# ---------------------------------------------------------------------------
# Status calculated per unique current chunk, not by summing attempts.
# ---------------------------------------------------------------------------


async def test_partial_current_identity_completion_is_reported_per_unique_chunk(
    session: AsyncSession,
    cleanup_ids: dict[str, list[uuid.UUID]],
    make_document_with_chunks,
) -> None:
    """3 of 4 chunks embedded under the current identity, plus every
    chunk also carrying an old-identity FAILED row: the summary must
    read "3 of 4", not be inflated or corrupted by the old rows."""
    document_id, _engagement_id, organization_id, chunk_ids = await make_document_with_chunks(4)
    contents = [f"Chunk {i}: emissions decreased year over year." for i in range(4)]
    embedding_repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)

    await _fail_under_identity(
        embedding_repository, cleanup_ids, chunk_ids, contents,
        organization_id=organization_id, model=OLD_MODEL
    )
    await _complete_under_identity(
        embedding_repository, cleanup_ids, chunk_ids[:3], contents[:3],
        organization_id=organization_id, model=CURRENT_MODEL
    )

    document_repository = SQLAlchemyDocumentRepository(session)
    read_model = await document_repository.get_read_model_for_organization(
        document_id,
        organization_id=organization_id,
        embedding_provider=PROVIDER,
        embedding_model=CURRENT_MODEL,
        embedding_model_version=MODEL_VERSION,
    )

    assert read_model is not None
    assert read_model.chunk_count == 4
    summary = read_model.embedding_summary
    assert summary.total_chunks == 3
    assert summary.completed == 3
    assert summary.failed == 0
    # `is_complete` means "every row attempted under this identity
    # succeeded" (true here: 3/3), not "every chunk in the document has
    # been attempted" -- per `EmbeddingSummary`'s own docstring, that
    # broader completeness is for the caller to judge by comparing
    # `total_chunks` against `chunk_count` itself, exactly as done here.
    assert summary.is_complete is True
    assert summary.total_chunks < read_model.chunk_count  # a real, unattempted 4th chunk remains


async def test_list_read_models_also_scopes_embedding_summary_to_current_identity(
    session: AsyncSession,
    cleanup_ids: dict[str, list[uuid.UUID]],
    make_document_with_chunks,
) -> None:
    document_id, _engagement_id, organization_id, chunk_ids = await make_document_with_chunks(1)
    contents = ["Chunk 0: emissions decreased year over year."]
    embedding_repository = SQLAlchemyDocumentChunkEmbeddingRepository(session)

    await _fail_under_identity(
        embedding_repository, cleanup_ids, chunk_ids, contents,
        organization_id=organization_id, model=OLD_MODEL
    )
    await _complete_under_identity(
        embedding_repository, cleanup_ids, chunk_ids, contents,
        organization_id=organization_id, model=CURRENT_MODEL
    )

    document_repository = SQLAlchemyDocumentRepository(session)
    items = await document_repository.list_read_models_for_organization(
        organization_id=organization_id,
        limit=50,
        offset=0,
        embedding_provider=PROVIDER,
        embedding_model=CURRENT_MODEL,
        embedding_model_version=MODEL_VERSION,
    )

    matching = [item for item in items if item.id == document_id]
    assert len(matching) == 1
    summary = matching[0].embedding_summary
    assert summary.total_chunks == 1
    assert summary.completed == 1
    assert summary.failed == 0
