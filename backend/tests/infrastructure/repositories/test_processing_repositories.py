"""Integration tests for the Sprint 3.5 (Document Processing Foundation)
persistence layer against a real database: ``SQLAlchemyExtractedTextRepository``,
``SQLAlchemyDocumentChunkRepository``, ``SQLAlchemyDocumentRepository``'s
``begin_processing``/``complete_processing``, and ``SQLAlchemyProcessingUnitOfWork``.

Follows the same conventions as ``test_document_repository.py``: real rows
against the configured ``DATABASE_URL``, randomized per test, cleaned up in
an independent session in teardown regardless of outcome. Cleanup order is
strict: document_chunks/extracted_text (children) before documents, before
engagements, before organizations -- matching the ``NO ACTION`` foreign
keys involved.

Marked ``integration`` module-wide, skipped by the default
``pytest -m "not integration"`` run.
"""

import asyncio
import uuid
from typing import AsyncIterator, Awaitable, Callable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    InvalidStateTransitionError,
    NotFoundError,
    PersistenceError,
)
from app.domain.entities.document_chunk import DocumentChunk
from app.domain.entities.extracted_text import ExtractedText
from app.infrastructure.db.models.document import DocumentModel
from app.infrastructure.db.models.document_chunk import DocumentChunkModel
from app.infrastructure.db.models.engagement import Engagement
from app.infrastructure.db.models.extracted_text import ExtractedText as ExtractedTextModel
from app.infrastructure.db.models.organization import Organization
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.processing_unit_of_work import SQLAlchemyProcessingUnitOfWork
from app.infrastructure.repositories.document import SQLAlchemyDocumentRepository
from app.infrastructure.repositories.document_chunk import SQLAlchemyDocumentChunkRepository
from app.infrastructure.repositories.extracted_text import SQLAlchemyExtractedTextRepository

pytestmark = pytest.mark.integration


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
        "chunks": [],
        "extracted_text": [],
        "documents": [],
        "engagements": [],
        "organizations": [],
    }
    yield ids
    async with AsyncSessionLocal() as cleanup_session:
        for chunk_id in ids["chunks"]:
            model = await cleanup_session.get(DocumentChunkModel, chunk_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for extracted_text_id in ids["extracted_text"]:
            model = await cleanup_session.get(ExtractedTextModel, extracted_text_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for document_id in ids["documents"]:
            model = await cleanup_session.get(DocumentModel, document_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for engagement_id in ids["engagements"]:
            model = await cleanup_session.get(Engagement, engagement_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for organization_id in ids["organizations"]:
            model = await cleanup_session.get(Organization, organization_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()


@pytest.fixture
def make_document(
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> Callable[..., Awaitable[uuid.UUID]]:
    """Factory: creates a real Organization + Engagement + Document row,
    returns the document's id. All rows are tracked in ``cleanup_ids`` for
    teardown."""

    async def _make(status: str = "PENDING") -> uuid.UUID:
        async with AsyncSessionLocal() as session:
            organization = Organization(name="Processing Repository Test Org")
            session.add(organization)
            await session.flush()
            engagement = Engagement(
                organization_id=organization.id,
                title="Processing Repository Test Engagement",
            )
            session.add(engagement)
            await session.flush()
            document = DocumentModel(
                filename="report.pdf",
                storage_path=f"test/{uuid.uuid4()}.pdf",
                processing_status=status,
                engagement_id=engagement.id,
            )
            session.add(document)
            await session.commit()
            await session.refresh(document)
        cleanup_ids["organizations"].append(organization.id)
        cleanup_ids["engagements"].append(engagement.id)
        cleanup_ids["documents"].append(document.id)
        return document.id

    return _make


@pytest.fixture
async def document_id(make_document: Callable[..., Awaitable[uuid.UUID]]) -> uuid.UUID:
    return await make_document()


async def _organization_of(document_id: uuid.UUID) -> uuid.UUID:
    """Resolve a document's owning organization through the real
    ``documents -> engagements`` join.

    MVP Slice 3 made ``organization_id`` mandatory on every tenant-owned
    repository method. Tests resolve it the same way production does --
    from the row's actual lineage -- rather than inventing a value, so a
    scope that stopped matching would fail here too.
    """

    async with AsyncSessionLocal() as session:
        document = await session.get(DocumentModel, document_id)
        assert document is not None
        engagement = await session.get(Engagement, document.engagement_id)
        assert engagement is not None
        assert engagement.organization_id is not None
        return engagement.organization_id


@pytest.fixture
async def organization_id(document_id: uuid.UUID) -> uuid.UUID:
    return await _organization_of(document_id)


# ---------------------------------------------------------------------------
# SQLAlchemyExtractedTextRepository
# ---------------------------------------------------------------------------


async def test_extracted_text_create_flushes_but_does_not_commit(
    session: AsyncSession,
    cleanup_ids: dict[str, list[uuid.UUID]],
    document_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> None:
    repository = SQLAlchemyExtractedTextRepository(session)

    created = await repository.create(
        ExtractedText(id=None, document_id=document_id, extracted_content="hello world", created_at=None)
    )
    cleanup_ids["extracted_text"].append(created.id)

    # Visible within the same, still-open transaction (flush, not commit)...
    fetched = await repository.get_by_document(document_id, organization_id=organization_id)
    assert fetched is not None
    assert fetched.extracted_content == "hello world"

    # ...but not yet visible from an independent session, since nothing was committed.
    async with AsyncSessionLocal() as other_session:
        other_result = await other_session.get(ExtractedTextModel, created.id)
        assert other_result is None

    await session.commit()

    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(ExtractedTextModel, created.id)
        assert model is not None
        assert model.extracted_content == "hello world"


async def test_extracted_text_get_by_document_returns_none_when_absent(
    session: AsyncSession, document_id: uuid.UUID, organization_id: uuid.UUID
) -> None:
    repository = SQLAlchemyExtractedTextRepository(session)
    assert await repository.get_by_document(document_id, organization_id=organization_id) is None


async def test_extracted_text_is_not_readable_from_another_organization(
    session: AsyncSession,
    cleanup_ids: dict[str, list[uuid.UUID]],
    document_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> None:
    """The row holds the document's full normalized text -- the largest
    single disclosure on this table. A real document id paired with a
    foreign organization must resolve to nothing."""

    repository = SQLAlchemyExtractedTextRepository(session)
    created = await repository.create(
        ExtractedText(id=None, document_id=document_id, extracted_content="secret", created_at=None)
    )
    await session.commit()
    cleanup_ids["extracted_text"].append(created.id)

    assert await repository.get_by_document(
        document_id, organization_id=organization_id
    ) is not None
    assert await repository.get_by_document(
        document_id, organization_id=uuid.uuid4()
    ) is None


async def test_extracted_text_unique_constraint_violation_maps_to_persistence_error(
    session: AsyncSession,
    cleanup_ids: dict[str, list[uuid.UUID]],
    document_id: uuid.UUID,
) -> None:
    repository = SQLAlchemyExtractedTextRepository(session)
    first = await repository.create(
        ExtractedText(id=None, document_id=document_id, extracted_content="first", created_at=None)
    )
    await session.commit()
    cleanup_ids["extracted_text"].append(first.id)

    with pytest.raises(PersistenceError):
        await repository.create(
            ExtractedText(id=None, document_id=document_id, extracted_content="second", created_at=None)
        )
    await session.rollback()


# ---------------------------------------------------------------------------
# SQLAlchemyDocumentChunkRepository
# ---------------------------------------------------------------------------


async def test_document_chunk_create_many_bulk_inserts_and_flushes(
    session: AsyncSession,
    cleanup_ids: dict[str, list[uuid.UUID]],
    document_id: uuid.UUID,
) -> None:
    repository = SQLAlchemyDocumentChunkRepository(session)

    created = await repository.create_many(
        [
            DocumentChunk(id=None, document_id=document_id, chunk_index=0, content="chunk zero", char_start=0, char_end=10, created_at=None),
            DocumentChunk(id=None, document_id=document_id, chunk_index=1, content="chunk one", char_start=0, char_end=9, created_at=None),
        ]
    )
    cleanup_ids["chunks"].extend(c.id for c in created)

    assert len(created) == 2
    async with AsyncSessionLocal() as other_session:
        for chunk in created:
            assert await other_session.get(DocumentChunkModel, chunk.id) is None

    await session.commit()

    async with AsyncSessionLocal() as verify_session:
        for chunk in created:
            model = await verify_session.get(DocumentChunkModel, chunk.id)
            assert model is not None


async def test_document_chunk_get_by_document_orders_by_chunk_index(
    session: AsyncSession,
    cleanup_ids: dict[str, list[uuid.UUID]],
    document_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> None:
    repository = SQLAlchemyDocumentChunkRepository(session)
    created = await repository.create_many(
        [
            DocumentChunk(id=None, document_id=document_id, chunk_index=2, content="c", char_start=0, char_end=1, created_at=None),
            DocumentChunk(id=None, document_id=document_id, chunk_index=0, content="a", char_start=0, char_end=1, created_at=None),
            DocumentChunk(id=None, document_id=document_id, chunk_index=1, content="b", char_start=0, char_end=1, created_at=None),
        ]
    )
    await session.commit()
    cleanup_ids["chunks"].extend(c.id for c in created)

    results = await repository.get_by_document(document_id, organization_id=organization_id)

    assert [c.chunk_index for c in results] == [0, 1, 2]
    assert [c.content for c in results] == ["a", "b", "c"]

    # Same real document id, foreign organization: no chunk text at all.
    assert await repository.get_by_document(document_id, organization_id=uuid.uuid4()) == []


async def test_document_chunk_get_by_document_returns_empty_when_none_exist(
    session: AsyncSession, document_id: uuid.UUID, organization_id: uuid.UUID
) -> None:
    repository = SQLAlchemyDocumentChunkRepository(session)
    assert await repository.get_by_document(document_id, organization_id=organization_id) == []


async def test_document_chunk_unique_constraint_violation_maps_to_persistence_error(
    session: AsyncSession,
    cleanup_ids: dict[str, list[uuid.UUID]],
    document_id: uuid.UUID,
) -> None:
    repository = SQLAlchemyDocumentChunkRepository(session)
    created = await repository.create_many(
        [DocumentChunk(id=None, document_id=document_id, chunk_index=0, content="first", char_start=0, char_end=5, created_at=None)]
    )
    await session.commit()
    cleanup_ids["chunks"].extend(c.id for c in created)

    with pytest.raises(PersistenceError):
        await repository.create_many(
            [DocumentChunk(id=None, document_id=document_id, chunk_index=0, content="dup", char_start=0, char_end=3, created_at=None)]
        )
    await session.rollback()


# ---------------------------------------------------------------------------
# begin_processing -- atomic claim, concurrency
# ---------------------------------------------------------------------------


async def test_begin_processing_claims_a_pending_document(
    session: AsyncSession, document_id: uuid.UUID, organization_id: uuid.UUID
) -> None:
    repository = SQLAlchemyDocumentRepository(session)

    claimed = await repository.begin_processing(document_id, organization_id=organization_id)

    assert claimed.processing_status == "PROCESSING"
    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(DocumentModel, document_id)
        assert model is not None
        assert model.processing_status == "PROCESSING"


async def test_begin_processing_raises_not_found_for_missing_document(
    session: AsyncSession,
) -> None:
    repository = SQLAlchemyDocumentRepository(session)
    with pytest.raises(NotFoundError):
        await repository.begin_processing(uuid.uuid4(), organization_id=uuid.uuid4())


async def test_begin_processing_never_claims_another_organizations_document(
    session: AsyncSession, document_id: uuid.UUID
) -> None:
    """The tenant predicate is inside the conditional UPDATE itself.

    A *real* PENDING document id with a foreign organization must raise the
    same ``NotFoundError`` an unknown id raises -- not
    ``InvalidStateTransitionError``, which would confirm the row exists --
    and must leave the row PENDING rather than claiming it.
    """

    repository = SQLAlchemyDocumentRepository(session)

    with pytest.raises(NotFoundError):
        await repository.begin_processing(document_id, organization_id=uuid.uuid4())

    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(DocumentModel, document_id)
        assert model is not None
        assert model.processing_status == "PENDING"  # never claimed


@pytest.mark.parametrize(
    "status,expected_message",
    [
        ("PROCESSING", "Document is already being processed."),
        ("PROCESSED", "Document has already been processed."),
        ("FAILED", "Failed documents cannot be reprocessed in this sprint."),
    ],
)
async def test_begin_processing_rejects_non_pending_states_with_exact_message(
    make_document: Callable[..., Awaitable[uuid.UUID]],
    status: str,
    expected_message: str,
) -> None:
    doc_id = await make_document(status=status)
    owner_id = await _organization_of(doc_id)
    async with AsyncSessionLocal() as session:
        repository = SQLAlchemyDocumentRepository(session)
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            await repository.begin_processing(doc_id, organization_id=owner_id)
        assert exc_info.value.message == expected_message
        assert exc_info.value.status_code == 409


async def test_begin_processing_two_concurrent_calls_only_one_wins(
    document_id: uuid.UUID, organization_id: uuid.UUID
) -> None:
    """The core concurrency guarantee: two callers racing to claim the same
    PENDING document must not both succeed. Uses two independent sessions
    (simulating two concurrent requests) issuing the conditional UPDATE
    sequentially -- proven sufficient because the guarantee comes from
    Postgres row-level locking + READ COMMITTED re-evaluation of the WHERE
    clause against the freshly committed value, not from any
    application-level ordering."""
    async with AsyncSessionLocal() as session_a:
        repository_a = SQLAlchemyDocumentRepository(session_a)
        first = await repository_a.begin_processing(
            document_id, organization_id=organization_id
        )
    assert first.processing_status == "PROCESSING"

    async with AsyncSessionLocal() as session_b:
        repository_b = SQLAlchemyDocumentRepository(session_b)
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            await repository_b.begin_processing(
                document_id, organization_id=organization_id
            )
    assert exc_info.value.message == "Document is already being processed."

    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(DocumentModel, document_id)
        assert model is not None
        assert model.processing_status == "PROCESSING"  # claimed exactly once


async def test_begin_processing_truly_concurrent_tasks_only_one_wins(
    document_id: uuid.UUID, organization_id: uuid.UUID
) -> None:
    """Same guarantee, exercised via genuinely concurrent asyncio tasks
    (not just sequential calls) against two independent sessions/connections."""

    async def _attempt() -> str:
        async with AsyncSessionLocal() as session:
            repository = SQLAlchemyDocumentRepository(session)
            try:
                await repository.begin_processing(
                    document_id, organization_id=organization_id
                )
                return "won"
            except InvalidStateTransitionError:
                return "lost"

    results = await asyncio.gather(_attempt(), _attempt())

    assert sorted(results) == ["lost", "won"]


# ---------------------------------------------------------------------------
# complete_processing -- flush-only, caller owns the commit
# ---------------------------------------------------------------------------


async def test_complete_processing_flushes_but_does_not_commit(
    session: AsyncSession, document_id: uuid.UUID, organization_id: uuid.UUID
) -> None:
    repository = SQLAlchemyDocumentRepository(session)
    await repository.begin_processing(document_id, organization_id=organization_id)

    completed = await repository.complete_processing(
        document_id, organization_id=organization_id
    )
    assert completed.processing_status == "PROCESSED"

    # Not yet visible to an independent session -- only flushed, not committed.
    async with AsyncSessionLocal() as other_session:
        model = await other_session.get(DocumentModel, document_id)
        assert model is not None
        assert model.processing_status == "PROCESSING"

    await session.commit()

    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(DocumentModel, document_id)
        assert model is not None
        assert model.processing_status == "PROCESSED"


async def test_complete_processing_raises_not_found_for_missing_document(
    session: AsyncSession,
) -> None:
    repository = SQLAlchemyDocumentRepository(session)
    with pytest.raises(NotFoundError):
        await repository.complete_processing(uuid.uuid4(), organization_id=uuid.uuid4())


async def test_complete_processing_never_writes_another_organizations_document(
    session: AsyncSession, document_id: uuid.UUID, organization_id: uuid.UUID
) -> None:
    repository = SQLAlchemyDocumentRepository(session)
    await repository.begin_processing(document_id, organization_id=organization_id)
    await session.commit()

    with pytest.raises(NotFoundError):
        await repository.complete_processing(document_id, organization_id=uuid.uuid4())

    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(DocumentModel, document_id)
        assert model is not None
        assert model.processing_status == "PROCESSING"  # not advanced by a foreign caller


# ---------------------------------------------------------------------------
# End-to-end transactional behavior via IProcessingUnitOfWork
# ---------------------------------------------------------------------------


async def test_unit_of_work_commit_persists_extracted_text_chunks_and_processed_status_together(
    session: AsyncSession,
    cleanup_ids: dict[str, list[uuid.UUID]],
    document_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> None:
    document_repository = SQLAlchemyDocumentRepository(session)
    extracted_text_repository = SQLAlchemyExtractedTextRepository(session)
    chunk_repository = SQLAlchemyDocumentChunkRepository(session)
    unit_of_work = SQLAlchemyProcessingUnitOfWork(session)

    await document_repository.begin_processing(document_id, organization_id=organization_id)
    created_text = await extracted_text_repository.create(
        ExtractedText(id=None, document_id=document_id, extracted_content="full text", created_at=None)
    )
    created_chunks = await chunk_repository.create_many(
        [DocumentChunk(id=None, document_id=document_id, chunk_index=0, content="full text", char_start=0, char_end=9, created_at=None)]
    )
    await document_repository.complete_processing(document_id, organization_id=organization_id)
    await unit_of_work.commit()

    cleanup_ids["extracted_text"].append(created_text.id)
    cleanup_ids["chunks"].extend(c.id for c in created_chunks)

    async with AsyncSessionLocal() as verify_session:
        document_model = await verify_session.get(DocumentModel, document_id)
        assert document_model is not None
        assert document_model.processing_status == "PROCESSED"

        text_model = await verify_session.get(ExtractedTextModel, created_text.id)
        assert text_model is not None
        assert text_model.extracted_content == "full text"

        chunk_model = await verify_session.get(DocumentChunkModel, created_chunks[0].id)
        assert chunk_model is not None


async def test_unit_of_work_rollback_leaves_no_extracted_text_or_chunk_rows(
    session: AsyncSession,
    document_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> None:
    document_repository = SQLAlchemyDocumentRepository(session)
    extracted_text_repository = SQLAlchemyExtractedTextRepository(session)
    chunk_repository = SQLAlchemyDocumentChunkRepository(session)
    unit_of_work = SQLAlchemyProcessingUnitOfWork(session)

    await document_repository.begin_processing(document_id, organization_id=organization_id)
    created_text = await extracted_text_repository.create(
        ExtractedText(id=None, document_id=document_id, extracted_content="doomed text", created_at=None)
    )
    created_chunks = await chunk_repository.create_many(
        [DocumentChunk(id=None, document_id=document_id, chunk_index=0, content="doomed", char_start=0, char_end=6, created_at=None)]
    )

    await unit_of_work.rollback()

    async with AsyncSessionLocal() as verify_session:
        assert await verify_session.get(ExtractedTextModel, created_text.id) is None
        assert await verify_session.get(DocumentChunkModel, created_chunks[0].id) is None
        # The document itself was already committed as PROCESSING by
        # begin_processing() -- rollback of the *processing* transaction
        # does not, and must not, undo that separate, already-committed
        # claim transaction.
        document_model = await verify_session.get(DocumentModel, document_id)
        assert document_model is not None
        assert document_model.processing_status == "PROCESSING"
