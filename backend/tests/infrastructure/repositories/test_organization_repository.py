"""Integration tests for ``SQLAlchemyOrganizationRepository`` against a real
database.

Mirrors ``test_document_repository.py``'s structure. Every test tracks the
ids it creates in ``cleanup_ids``, which deletes them via an independent
session in teardown, regardless of test outcome. Unlike ``Document``,
``Organization`` has no foreign-key dependents in this sprint's scope, so
there is no cross-entity teardown ordering to manage.

Marked ``integration`` module-wide so the default CI run
(``pytest -m "not integration"``) skips this file entirely.
"""

import uuid
from typing import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.domain.entities.organization import Organization
from app.infrastructure.db.models.organization import Organization as OrganizationModel
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.repositories.organization import SQLAlchemyOrganizationRepository

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
async def repository(session: AsyncSession) -> SQLAlchemyOrganizationRepository:
    return SQLAlchemyOrganizationRepository(session)


@pytest.fixture
async def cleanup_ids() -> AsyncIterator[list[uuid.UUID]]:
    ids: list[uuid.UUID] = []
    yield ids
    if not ids:
        return
    async with AsyncSessionLocal() as cleanup_session:
        for organization_id in ids:
            model = await cleanup_session.get(OrganizationModel, organization_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()


# ---------------------------------------------------------------------------
# 1. Create
# ---------------------------------------------------------------------------


async def test_create_persists_organization_with_server_generated_id_and_created_at(
    repository: SQLAlchemyOrganizationRepository, cleanup_ids: list[uuid.UUID]
) -> None:
    created = await repository.create(Organization(id=None, name="Acme Corp", created_at=None))
    assert created.id is not None
    cleanup_ids.append(created.id)

    assert isinstance(created.id, uuid.UUID)
    assert created.name == "Acme Corp"
    assert created.created_at is not None

    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(OrganizationModel, created.id)
        assert model is not None
        assert model.name == "Acme Corp"


# ---------------------------------------------------------------------------
# 2. Read
# ---------------------------------------------------------------------------


async def test_get_for_organization_retrieves_the_tenant_root_by_its_own_id(
    repository: SQLAlchemyOrganizationRepository, cleanup_ids: list[uuid.UUID]
) -> None:
    created = await repository.create(Organization(id=None, name="Get Org", created_at=None))
    assert created.id is not None
    cleanup_ids.append(created.id)

    fetched = await repository.get_for_organization(created.id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.name == "Get Org"


async def test_get_for_organization_returns_none_for_missing_id(
    repository: SQLAlchemyOrganizationRepository,
) -> None:
    assert await repository.get_for_organization(uuid.uuid4()) is None


async def test_the_repository_offers_no_global_listing_or_count(
    repository: SQLAlchemyOrganizationRepository, cleanup_ids: list[uuid.UUID]
) -> None:
    """MVP Slice 3 closure. ``list()`` and ``count()`` used to exist here
    and were global across every tenant -- one enumerating all
    organizations by name, the other disclosing how many exist.

    This replaces the three tests that exercised them. It is deliberately
    a structural assertion rather than a behavioural one: the point is
    that the methods are *gone*, so no caller can reach a cross-tenant
    result, not that some particular caller currently avoids them. Rows
    are still created here so the check runs against a repository with
    real data behind it.
    """

    for index in range(2):
        created = await repository.create(
            Organization(id=None, name=f"No Global Listing {index}", created_at=None)
        )
        assert created.id is not None
        cleanup_ids.append(created.id)

    assert not hasattr(repository, "list")
    assert not hasattr(repository, "count")
    # The only read this repository offers is the scoped one.
    assert hasattr(repository, "get_for_organization")


# ---------------------------------------------------------------------------
# 3. Update
# ---------------------------------------------------------------------------


async def test_update_changes_name_and_preserves_created_at(
    repository: SQLAlchemyOrganizationRepository, cleanup_ids: list[uuid.UUID]
) -> None:
    created = await repository.create(Organization(id=None, name="Old Name", created_at=None))
    assert created.id is not None
    cleanup_ids.append(created.id)

    updated = await repository.update(
        Organization(id=created.id, name="New Name", created_at=created.created_at)
    )

    assert updated.name == "New Name"
    assert updated.created_at == created.created_at

    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(OrganizationModel, created.id)
        assert model is not None
        assert model.name == "New Name"


async def test_update_raises_not_found_for_missing_organization(
    repository: SQLAlchemyOrganizationRepository,
) -> None:
    with pytest.raises(NotFoundError):
        await repository.update(
            Organization(id=uuid.uuid4(), name="Nonexistent", created_at=None)
        )


# ---------------------------------------------------------------------------
# 4. Transaction validation
# ---------------------------------------------------------------------------


async def test_commit_persists_across_independent_sessions(
    repository: SQLAlchemyOrganizationRepository, cleanup_ids: list[uuid.UUID]
) -> None:
    created = await repository.create(Organization(id=None, name="Commit Org", created_at=None))
    assert created.id is not None
    cleanup_ids.append(created.id)

    async with AsyncSessionLocal() as other_session:
        model = await other_session.get(OrganizationModel, created.id)
        assert model is not None


async def test_rollback_discards_uncommitted_changes() -> None:
    organization_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        model = OrganizationModel(id=organization_id, name="Rollback Org")
        session.add(model)
        await session.flush()

        assert await session.get(OrganizationModel, organization_id) is not None

        await session.rollback()

    async with AsyncSessionLocal() as verify_session:
        assert await verify_session.get(OrganizationModel, organization_id) is None


# ---------------------------------------------------------------------------
# 5. Cleanup-only delete (not a supported application capability -- see
#    IOrganizationRepository's docstring)
# ---------------------------------------------------------------------------


async def test_delete_removes_the_record(
    repository: SQLAlchemyOrganizationRepository,
) -> None:
    created = await repository.create(Organization(id=None, name="Delete Org", created_at=None))
    assert created.id is not None

    await repository.delete(created)

    assert await repository.get_for_organization(created.id) is None
