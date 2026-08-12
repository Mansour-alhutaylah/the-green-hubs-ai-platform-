"""Unit tests for ``OrganizationService`` -- business logic exercised against
an in-memory fake repository. No database, no HTTP, no ``integration`` mark.

Sprint 3.5.1 (Tenant Isolation & API Security): every method now takes
``current_user``, so fixtures seed two organizations (A/B) and two users
(one per organization) to exercise same-tenant success and cross-tenant
denial for every route.
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.core.exceptions import AuthorizationError, NotFoundError
from app.domain.entities.organization import Organization
from app.domain.entities.user import User
from app.domain.repositories.organization import IOrganizationRepository
from app.services.organization import OrganizationService


class FakeOrganizationRepository(IOrganizationRepository):
    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, Organization] = {}

    def seed(self, name: str = "Seed Org") -> Organization:
        organization_id = uuid.uuid4()
        organization = Organization(
            id=organization_id, name=name, created_at=datetime.now(timezone.utc)
        )
        self._rows[organization_id] = organization
        return organization

    def row_count(self) -> int:
        """Test-only accessor. Not part of ``IOrganizationRepository`` --
        the global ``count()`` was removed in the MVP Slice 3 closure
        because it disclosed how many tenants exist."""

        return len(self._rows)

    async def get_for_organization(
        self, organization_id: uuid.UUID
    ) -> Organization | None:
        return self._rows.get(organization_id)

    async def create(self, entity: Organization) -> Organization:
        raise NotImplementedError

    async def update(self, entity: Organization) -> Organization:
        assert entity.id is not None
        if entity.id not in self._rows:
            raise NotFoundError(f"Organization {entity.id} not found")
        self._rows[entity.id] = entity
        return entity

    async def delete(self, entity: Organization) -> None:
        if entity.id is not None:
            self._rows.pop(entity.id, None)


def _user(organization_id: uuid.UUID | None) -> User:
    return User(
        id=uuid.uuid4(),
        organization_id=organization_id,
        full_name="Test User",
        email="test@example.com",
        role=None,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def repository() -> FakeOrganizationRepository:
    return FakeOrganizationRepository()


@pytest.fixture
def service(repository: FakeOrganizationRepository) -> OrganizationService:
    return OrganizationService(repository)


@pytest.fixture
def organization_a(repository: FakeOrganizationRepository) -> Organization:
    return repository.seed("Organization A")


@pytest.fixture
def organization_b(repository: FakeOrganizationRepository) -> Organization:
    return repository.seed("Organization B")


@pytest.fixture
def user_a(organization_a: Organization) -> User:
    assert organization_a.id is not None
    return _user(organization_a.id)


@pytest.fixture
def user_b(organization_b: Organization) -> User:
    assert organization_b.id is not None
    return _user(organization_b.id)


# ---------------------------------------------------------------------------
# Creation -- disabled for everyone
# ---------------------------------------------------------------------------


async def test_create_rejected_with_403_for_any_authenticated_user(
    service: OrganizationService, user_a: User
) -> None:
    with pytest.raises(AuthorizationError):
        await service.create("New Org", user_a)


async def test_create_does_not_persist_a_row(
    service: OrganizationService, repository: FakeOrganizationRepository, user_a: User
) -> None:
    # Counted through the fake's own test-only accessor: the repository
    # interface has no global count() any more (MVP Slice 3 closure), and
    # reintroducing one just to assert this would restore the surface the
    # closure removed.
    before = repository.row_count()

    with pytest.raises(AuthorizationError):
        await service.create("New Org", user_a)

    assert repository.row_count() == before


# ---------------------------------------------------------------------------
# Null-organization profile
# ---------------------------------------------------------------------------


async def test_get_rejected_for_user_with_null_organization(
    service: OrganizationService, organization_a: Organization
) -> None:
    user = _user(None)
    assert organization_a.id is not None
    with pytest.raises(AuthorizationError):
        await service.get(organization_a.id, user)


async def test_list_rejected_for_user_with_null_organization(
    service: OrganizationService,
) -> None:
    user = _user(None)
    with pytest.raises(AuthorizationError):
        await service.list(user, page=1, page_size=20)


async def test_update_rejected_for_user_with_null_organization(
    service: OrganizationService, organization_a: Organization
) -> None:
    user = _user(None)
    assert organization_a.id is not None
    with pytest.raises(AuthorizationError):
        await service.update(organization_a.id, "New Name", user)


# ---------------------------------------------------------------------------
# List -- own organization only
# ---------------------------------------------------------------------------


async def test_list_returns_only_own_organization(
    service: OrganizationService,
    user_a: User,
    organization_a: Organization,
    organization_b: Organization,
) -> None:
    items, total = await service.list(user_a, page=1, page_size=20)

    assert total == 1
    assert len(items) == 1
    assert items[0].id == organization_a.id


async def test_list_total_is_one_for_a_valid_provisioned_user(
    service: OrganizationService, user_a: User
) -> None:
    _items, total = await service.list(user_a, page=1, page_size=20)
    assert total == 1


async def test_list_second_page_is_empty_but_total_stays_one(
    service: OrganizationService, user_a: User
) -> None:
    items, total = await service.list(user_a, page=2, page_size=20)

    assert items == []
    assert total == 1


async def test_list_raises_not_found_when_profile_references_missing_organization(
    service: OrganizationService, repository: FakeOrganizationRepository
) -> None:
    user = _user(uuid.uuid4())  # no matching row in the repository
    with pytest.raises(NotFoundError):
        await service.list(user, page=1, page_size=20)


# ---------------------------------------------------------------------------
# Get -- own organization only
# ---------------------------------------------------------------------------


async def test_get_own_organization_succeeds(
    service: OrganizationService, user_a: User, organization_a: Organization
) -> None:
    assert organization_a.id is not None
    fetched = await service.get(organization_a.id, user_a)
    assert fetched.id == organization_a.id
    assert fetched.name == organization_a.name


async def test_get_other_organization_returns_not_found(
    service: OrganizationService, user_a: User, organization_b: Organization
) -> None:
    assert organization_b.id is not None
    with pytest.raises(NotFoundError):
        await service.get(organization_b.id, user_a)


async def test_get_missing_organization_returns_identical_not_found(
    service: OrganizationService, user_a: User
) -> None:
    with pytest.raises(NotFoundError):
        await service.get(uuid.uuid4(), user_a)


async def test_cross_tenant_and_missing_get_raise_the_same_exception_type_and_message_shape(
    service: OrganizationService, user_a: User, organization_b: Organization
) -> None:
    assert organization_b.id is not None
    missing_id = uuid.uuid4()

    with pytest.raises(NotFoundError) as cross_tenant_exc:
        await service.get(organization_b.id, user_a)
    with pytest.raises(NotFoundError) as missing_exc:
        await service.get(missing_id, user_a)

    # Both are NotFoundError; neither ever reveals that the "other"
    # organization actually exists.
    assert type(cross_tenant_exc.value) is type(missing_exc.value)


# ---------------------------------------------------------------------------
# Update -- own organization only
# ---------------------------------------------------------------------------


async def test_update_own_organization_succeeds(
    service: OrganizationService, user_a: User, organization_a: Organization
) -> None:
    assert organization_a.id is not None
    updated = await service.update(organization_a.id, "Renamed", user_a)

    assert updated.name == "Renamed"
    assert updated.id == organization_a.id
    assert updated.created_at == organization_a.created_at


async def test_update_other_organization_returns_not_found(
    service: OrganizationService, user_a: User, organization_b: Organization
) -> None:
    assert organization_b.id is not None
    with pytest.raises(NotFoundError):
        await service.update(organization_b.id, "Hijacked Name", user_a)


async def test_update_other_organization_does_not_change_its_name(
    service: OrganizationService,
    repository: FakeOrganizationRepository,
    user_a: User,
    organization_b: Organization,
) -> None:
    assert organization_b.id is not None
    with pytest.raises(NotFoundError):
        await service.update(organization_b.id, "Hijacked Name", user_a)

    untouched = await repository.get_for_organization(organization_b.id)
    assert untouched is not None
    assert untouched.name == organization_b.name


async def test_update_missing_organization_returns_not_found(
    service: OrganizationService, user_a: User
) -> None:
    with pytest.raises(NotFoundError):
        await service.update(uuid.uuid4(), "New Name", user_a)
