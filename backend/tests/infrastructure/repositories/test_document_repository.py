"""Integration tests for ``SQLAlchemyDocumentRepository`` against a real database.

These tests exercise the repository against the actual configured
``DATABASE_URL`` (Supabase) rather than a mock or in-memory substitute --
the point of this validation is to prove the ORM mapping, session
lifecycle, and transaction behavior work against the real backend the app
ships against. Every test creates its own randomized rows; the
``cleanup_ids`` fixture removes them via an independent session in
teardown, which runs whether the test passes or fails.

``Document`` (the domain entity) has no ``updated_at`` field, so a few
assertions here read ``DocumentModel`` directly through a fresh session --
that is a deliberate, read-only probe of persisted state, not a domain- or
infrastructure-layer change.

Marked ``integration`` module-wide so the default CI run (``pytest -m "not
integration"``) skips this file entirely -- it needs a real, reachable
``DATABASE_URL`` and is meant to be run locally/deliberately via
``pytest -m integration``, not on every push against the shared dev
Supabase instance.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.domain.entities.document import Document
from app.infrastructure.db.models.document import DocumentModel
from app.infrastructure.db.session import AsyncSessionLocal, get_db
from app.infrastructure.repositories.document import SQLAlchemyDocumentRepository

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _require_database_url() -> None:
    """Explicit, readable failure when someone runs `-m integration` without
    a reachable database configured, instead of an opaque connection error."""
    if not get_settings().database_url:
        pytest.skip("integration tests require DATABASE_URL to be set")


def _make_document(**overrides: object) -> Document:
    defaults: dict = {
        "id": uuid.uuid4(),
        "filename": "sustainability-report.pdf",
        "storage_path": f"test/{uuid.uuid4()}.pdf",
        "processing_status": "PENDING",
        "engagement_id": uuid.uuid4(),
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return Document(**defaults)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def repository(session: AsyncSession) -> SQLAlchemyDocumentRepository:
    return SQLAlchemyDocumentRepository(session)


@pytest.fixture
async def cleanup_ids() -> AsyncIterator[list[uuid.UUID]]:
    """Track document ids created by a test; delete them after, regardless of outcome."""
    ids: list[uuid.UUID] = []
    yield ids
    if not ids:
        return
    async with AsyncSessionLocal() as cleanup_session:
        for document_id in ids:
            model = await cleanup_session.get(DocumentModel, document_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()


# ---------------------------------------------------------------------------
# 1. Create
# ---------------------------------------------------------------------------


async def test_create_persists_document_with_uuid_timestamps_and_status(
    repository: SQLAlchemyDocumentRepository,
    cleanup_ids: list[uuid.UUID],
) -> None:
    document = _make_document(processing_status="PENDING")

    created = await repository.create(document)
    cleanup_ids.append(created.id)

    assert isinstance(created, Document)
    assert isinstance(created.id, uuid.UUID)
    assert created.id == document.id
    assert created.processing_status == "PENDING"
    assert isinstance(created.created_at, datetime)
    assert created.created_at.tzinfo is not None  # timezone-aware, not naive

    # Confirm it is genuinely persisted, via an independent session/connection.
    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(DocumentModel, created.id)
        assert model is not None
        assert model.filename == document.filename
        assert model.storage_path == document.storage_path
        assert model.updated_at is not None
        assert model.updated_at.tzinfo is not None


async def test_new_row_defaults_processing_status_at_schema_level(
    session: AsyncSession,
    cleanup_ids: list[uuid.UUID],
) -> None:
    """Insert a raw ORM row with no explicit status to prove the column default
    (not just application-supplied "PENDING") is what the schema declares."""
    model = DocumentModel(
        id=uuid.uuid4(),
        filename="no-status-supplied.pdf",
        storage_path=f"test/{uuid.uuid4()}.pdf",
        engagement_id=uuid.uuid4(),
    )
    session.add(model)
    await session.commit()
    await session.refresh(model)
    cleanup_ids.append(model.id)

    assert model.processing_status == "PENDING"


# ---------------------------------------------------------------------------
# 2. Read
# ---------------------------------------------------------------------------


async def test_get_retrieves_by_id(
    repository: SQLAlchemyDocumentRepository,
    cleanup_ids: list[uuid.UUID],
) -> None:
    created = await repository.create(_make_document())
    cleanup_ids.append(created.id)

    fetched = await repository.get(created.id)

    assert fetched is not None
    assert isinstance(fetched, Document)
    assert fetched.id == created.id
    assert fetched.filename == created.filename


async def test_get_returns_none_for_missing_id(
    repository: SQLAlchemyDocumentRepository,
) -> None:
    assert await repository.get(uuid.uuid4()) is None


async def test_get_by_engagement_returns_only_matching_documents(
    repository: SQLAlchemyDocumentRepository,
    cleanup_ids: list[uuid.UUID],
) -> None:
    engagement_id = uuid.uuid4()
    other_engagement_id = uuid.uuid4()

    first = await repository.create(_make_document(engagement_id=engagement_id))
    second = await repository.create(_make_document(engagement_id=engagement_id))
    unrelated = await repository.create(_make_document(engagement_id=other_engagement_id))
    cleanup_ids.extend([first.id, second.id, unrelated.id])

    results = await repository.get_by_engagement(engagement_id)

    assert {d.id for d in results} == {first.id, second.id}
    assert all(isinstance(d, Document) for d in results)
    assert all(d.engagement_id == engagement_id for d in results)


# ---------------------------------------------------------------------------
# 3. Update
# ---------------------------------------------------------------------------


async def test_update_status_changes_status_and_bumps_updated_at(
    repository: SQLAlchemyDocumentRepository,
    session: AsyncSession,
    cleanup_ids: list[uuid.UUID],
) -> None:
    created = await repository.create(_make_document(processing_status="PENDING"))
    cleanup_ids.append(created.id)

    before = await session.get(DocumentModel, created.id)
    assert before is not None
    updated_at_before = before.updated_at

    # Guarantee the next transaction's `now()` differs from the first's.
    await asyncio.sleep(0.05)

    updated = await repository.update_status(created.id, "PROCESSED")

    assert isinstance(updated, Document)
    assert not isinstance(updated, DocumentModel)
    assert updated.processing_status == "PROCESSED"

    async with AsyncSessionLocal() as verify_session:
        after = await verify_session.get(DocumentModel, created.id)
        assert after is not None
        assert after.processing_status == "PROCESSED"
        assert after.updated_at > updated_at_before


async def test_update_status_raises_not_found_for_missing_document(
    repository: SQLAlchemyDocumentRepository,
) -> None:
    with pytest.raises(NotFoundError):
        await repository.update_status(uuid.uuid4(), "PROCESSED")


# ---------------------------------------------------------------------------
# 4. Delete
# ---------------------------------------------------------------------------


async def test_delete_removes_the_record(
    repository: SQLAlchemyDocumentRepository,
) -> None:
    created = await repository.create(_make_document())

    await repository.delete(created)

    assert await repository.get(created.id) is None
    async with AsyncSessionLocal() as verify_session:
        assert await verify_session.get(DocumentModel, created.id) is None


# ---------------------------------------------------------------------------
# 5. Transaction validation
# ---------------------------------------------------------------------------


async def test_commit_persists_across_independent_sessions(
    repository: SQLAlchemyDocumentRepository,
    cleanup_ids: list[uuid.UUID],
) -> None:
    created = await repository.create(_make_document())
    cleanup_ids.append(created.id)

    async with AsyncSessionLocal() as other_session:
        model = await other_session.get(DocumentModel, created.id)
        assert model is not None


async def test_rollback_discards_uncommitted_changes() -> None:
    document = _make_document()

    async with AsyncSessionLocal() as session:
        model = DocumentModel(
            id=document.id,
            filename=document.filename,
            storage_path=document.storage_path,
            processing_status=document.processing_status,
            engagement_id=document.engagement_id,
        )
        session.add(model)
        await session.flush()  # sent to the DB, but not yet committed

        # Visible within the same, still-open transaction.
        assert await session.get(DocumentModel, document.id) is not None

        await session.rollback()

    # A separate transaction must never observe the rolled-back row.
    async with AsyncSessionLocal() as verify_session:
        assert await verify_session.get(DocumentModel, document.id) is None


# ---------------------------------------------------------------------------
# 6. Async session validation
# ---------------------------------------------------------------------------


async def test_session_opens_and_closes_cleanly() -> None:
    async with AsyncSessionLocal() as session:
        assert session.in_transaction() is False
        await session.execute(text("SELECT 1"))
        assert session.in_transaction() is True
    assert session.in_transaction() is False


async def test_get_db_yields_a_distinct_session_per_call() -> None:
    gen_a = get_db()
    session_a = await gen_a.__anext__()
    gen_b = get_db()
    session_b = await gen_b.__anext__()

    assert session_a is not session_b

    for gen in (gen_a, gen_b):
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()

    assert session_a.in_transaction() is False
    assert session_b.in_transaction() is False
