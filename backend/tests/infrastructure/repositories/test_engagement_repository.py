"""Integration tests for ``SQLAlchemyEngagementRepository`` against a real
database.

Mirrors ``test_organization_repository.py``. Every test that creates an
Engagement first creates a real Organization row (via ``make_organization``)
to satisfy the foreign key, and both are cleaned up in dependency-safe
order -- engagements before organizations -- via an independent session in
teardown, regardless of outcome.

Marked ``integration`` module-wide so the default CI run
(``pytest -m "not integration"``) skips this file entirely.
"""

import uuid
from typing import AsyncIterator, Awaitable, Callable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.domain.entities.engagement import Engagement
from app.infrastructure.db.models.engagement import Engagement as EngagementModel
from app.infrastructure.db.models.organization import Organization as OrganizationModel
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.repositories.engagement import SQLAlchemyEngagementRepository

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
async def repository(session: AsyncSession) -> SQLAlchemyEngagementRepository:
    return SQLAlchemyEngagementRepository(session)


@pytest.fixture
async def cleanup_ids() -> AsyncIterator[dict[str, list[uuid.UUID]]]:
    ids: dict[str, list[uuid.UUID]] = {"engagements": [], "organizations": []}
    yield ids
    async with AsyncSessionLocal() as cleanup_session:
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
async def make_organization(
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> Callable[[], Awaitable[uuid.UUID]]:
    async def _make() -> uuid.UUID:
        async with AsyncSessionLocal() as session:
            model = OrganizationModel(name="Engagement Repository Test Org")
            session.add(model)
            await session.commit()
            await session.refresh(model)
        cleanup_ids["organizations"].append(model.id)
        return model.id

    return _make


@pytest.fixture
async def organization_id(
    make_organization: Callable[[], Awaitable[uuid.UUID]],
) -> uuid.UUID:
    return await make_organization()


# ---------------------------------------------------------------------------
# 1. Create
# ---------------------------------------------------------------------------


async def test_create_persists_engagement_with_server_generated_id_and_created_at(
    repository: SQLAlchemyEngagementRepository,
    cleanup_ids: dict[str, list[uuid.UUID]],
    organization_id: uuid.UUID,
) -> None:
    created = await repository.create(
        Engagement(
            id=None,
            organization_id=organization_id,
            title="Audit 2026",
            status="planning",
            created_at=None,
        )
    )
    assert created.id is not None
    cleanup_ids["engagements"].append(created.id)

    assert isinstance(created.id, uuid.UUID)
    assert created.organization_id == organization_id
    assert created.title == "Audit 2026"
    assert created.status == "planning"
    assert created.created_at is not None


# ---------------------------------------------------------------------------
# 2. Read
# ---------------------------------------------------------------------------


async def test_get_retrieves_by_id(
    repository: SQLAlchemyEngagementRepository,
    cleanup_ids: dict[str, list[uuid.UUID]],
    organization_id: uuid.UUID,
) -> None:
    created = await repository.create(
        Engagement(
            id=None,
            organization_id=organization_id,
            title="Get Engagement",
            status="planning",
            created_at=None,
        )
    )
    assert created.id is not None
    cleanup_ids["engagements"].append(created.id)

    fetched = await repository.get_for_organization(
        created.id, organization_id=organization_id
    )

    assert fetched is not None
    assert fetched.id == created.id


async def test_get_for_organization_returns_none_for_missing_id(
    repository: SQLAlchemyEngagementRepository,
) -> None:
    assert (
        await repository.get_for_organization(
            uuid.uuid4(), organization_id=uuid.uuid4()
        )
        is None
    )


async def test_the_repository_offers_no_unscoped_read(
    repository: SQLAlchemyEngagementRepository,
) -> None:
    """MVP Slice 3 closure: the inherited unscoped ``get`` is gone, so a
    cross-tenant Engagement id cannot be resolved by any method here."""

    assert not hasattr(repository, "get")
    assert hasattr(repository, "get_for_organization")


async def test_list_returns_created_rows_in_deterministic_order(
    repository: SQLAlchemyEngagementRepository,
    cleanup_ids: dict[str, list[uuid.UUID]],
    organization_id: uuid.UUID,
) -> None:
    first = await repository.create(
        Engagement(
            id=None,
            organization_id=organization_id,
            title="Order A",
            status="planning",
            created_at=None,
        )
    )
    second = await repository.create(
        Engagement(
            id=None,
            organization_id=organization_id,
            title="Order B",
            status="planning",
            created_at=None,
        )
    )
    assert first.id is not None and second.id is not None
    cleanup_ids["engagements"].extend([first.id, second.id])

    results = await repository.list(organization_id=organization_id, limit=1000, offset=0)

    ids_in_order = [r.id for r in results]
    assert ids_in_order.index(first.id) < ids_in_order.index(second.id)


async def test_list_filters_by_organization_id(
    repository: SQLAlchemyEngagementRepository,
    cleanup_ids: dict[str, list[uuid.UUID]],
    make_organization: Callable[[], Awaitable[uuid.UUID]],
) -> None:
    org_a = await make_organization()
    org_b = await make_organization()
    engagement_a = await repository.create(
        Engagement(
            id=None, organization_id=org_a, title="Filter A", status="planning", created_at=None
        )
    )
    engagement_b = await repository.create(
        Engagement(
            id=None, organization_id=org_b, title="Filter B", status="planning", created_at=None
        )
    )
    assert engagement_a.id is not None and engagement_b.id is not None
    cleanup_ids["engagements"].extend([engagement_a.id, engagement_b.id])

    results = await repository.list(organization_id=org_a, limit=1000, offset=0)

    ids = [r.id for r in results]
    assert engagement_a.id in ids
    assert engagement_b.id not in ids


async def test_list_pagination_respects_limit_and_offset(
    repository: SQLAlchemyEngagementRepository,
    cleanup_ids: dict[str, list[uuid.UUID]],
    organization_id: uuid.UUID,
) -> None:
    created_ids = []
    for i in range(3):
        created = await repository.create(
            Engagement(
                id=None,
                organization_id=organization_id,
                title=f"Paginated Engagement {i}",
                status="planning",
                created_at=None,
            )
        )
        assert created.id is not None
        created_ids.append(created.id)
    cleanup_ids["engagements"].extend(created_ids)

    page = await repository.list(organization_id=organization_id, limit=1, offset=1)

    assert len(page) == 1


async def test_count_reflects_created_rows_and_respects_filter(
    repository: SQLAlchemyEngagementRepository,
    cleanup_ids: dict[str, list[uuid.UUID]],
    organization_id: uuid.UUID,
) -> None:
    before = await repository.count(organization_id=organization_id)

    created = await repository.create(
        Engagement(
            id=None,
            organization_id=organization_id,
            title="Count Engagement",
            status="planning",
            created_at=None,
        )
    )
    assert created.id is not None
    cleanup_ids["engagements"].append(created.id)

    after = await repository.count(organization_id=organization_id)

    assert after == before + 1


# ---------------------------------------------------------------------------
# 3. Update
# ---------------------------------------------------------------------------


async def test_update_changes_fields_and_preserves_created_at(
    repository: SQLAlchemyEngagementRepository,
    cleanup_ids: dict[str, list[uuid.UUID]],
    organization_id: uuid.UUID,
) -> None:
    created = await repository.create(
        Engagement(
            id=None,
            organization_id=organization_id,
            title="Old Title",
            status="planning",
            created_at=None,
        )
    )
    assert created.id is not None
    cleanup_ids["engagements"].append(created.id)

    updated = await repository.update(
        Engagement(
            id=created.id,
            organization_id=organization_id,
            title="New Title",
            status="active",
            created_at=created.created_at,
        )
    )

    assert updated.title == "New Title"
    assert updated.status == "active"
    assert updated.created_at == created.created_at


async def test_update_raises_not_found_for_missing_engagement(
    repository: SQLAlchemyEngagementRepository, organization_id: uuid.UUID
) -> None:
    with pytest.raises(NotFoundError):
        await repository.update(
            Engagement(
                id=uuid.uuid4(),
                organization_id=organization_id,
                title="Nonexistent",
                status="planning",
                created_at=None,
            )
        )


# ---------------------------------------------------------------------------
# 4. Transaction validation
# ---------------------------------------------------------------------------


async def test_commit_persists_across_independent_sessions(
    repository: SQLAlchemyEngagementRepository,
    cleanup_ids: dict[str, list[uuid.UUID]],
    organization_id: uuid.UUID,
) -> None:
    created = await repository.create(
        Engagement(
            id=None,
            organization_id=organization_id,
            title="Commit Engagement",
            status="planning",
            created_at=None,
        )
    )
    assert created.id is not None
    cleanup_ids["engagements"].append(created.id)

    async with AsyncSessionLocal() as other_session:
        model = await other_session.get(EngagementModel, created.id)
        assert model is not None


async def test_rollback_discards_uncommitted_changes(organization_id: uuid.UUID) -> None:
    engagement_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        model = EngagementModel(
            id=engagement_id,
            organization_id=organization_id,
            title="Rollback Engagement",
            status="planning",
        )
        session.add(model)
        await session.flush()

        assert await session.get(EngagementModel, engagement_id) is not None

        await session.rollback()

    async with AsyncSessionLocal() as verify_session:
        assert await verify_session.get(EngagementModel, engagement_id) is None


# ---------------------------------------------------------------------------
# 5. Cleanup-only delete (not a supported application capability -- see
#    IEngagementRepository's docstring)
# ---------------------------------------------------------------------------


async def test_delete_removes_the_record(
    repository: SQLAlchemyEngagementRepository, organization_id: uuid.UUID
) -> None:
    created = await repository.create(
        Engagement(
            id=None,
            organization_id=organization_id,
            title="Delete Engagement",
            status="planning",
            created_at=None,
        )
    )
    assert created.id is not None

    await repository.delete(created)

    assert (
        await repository.get_for_organization(
            created.id, organization_id=organization_id
        )
        is None
    )
