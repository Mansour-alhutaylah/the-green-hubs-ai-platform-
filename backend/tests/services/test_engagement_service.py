"""Unit tests for ``EngagementService`` -- business logic exercised against
in-memory fake repositories. No database, no HTTP, no ``integration`` mark.

Sprint 3.5.1 (Tenant Isolation & API Security): every method now takes
``current_user``, so fixtures seed two organizations (A/B) and two users
(one per organization) to exercise same-tenant success and cross-tenant
denial for every route.
"""

import uuid
from datetime import datetime, timezone
from typing import Sequence

import pytest

from app.core.exceptions import AuthorizationError, NotFoundError
from app.domain.entities.engagement import Engagement
from app.domain.entities.organization import Organization
from app.domain.entities.user import User
from app.domain.repositories.engagement import IEngagementRepository
from app.domain.repositories.organization import IOrganizationRepository
from app.services.engagement import EngagementService


class FakeEngagementRepository(IEngagementRepository):
    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, Engagement] = {}

    def seed(self, organization_id: uuid.UUID, title: str = "Seed Engagement") -> Engagement:
        engagement_id = uuid.uuid4()
        engagement = Engagement(
            id=engagement_id,
            organization_id=organization_id,
            title=title,
            status="planning",
            created_at=datetime.now(timezone.utc),
        )
        self._rows[engagement_id] = engagement
        return engagement


    async def list(
        self, *, organization_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> Sequence[Engagement]:
        rows = [e for e in self._rows.values() if e.organization_id == organization_id]
        rows.sort(key=lambda e: (e.created_at, str(e.id)))
        return rows[offset : offset + limit]

    async def count(self, *, organization_id: uuid.UUID) -> int:
        return len([e for e in self._rows.values() if e.organization_id == organization_id])

    async def get_for_organization(
        self, entity_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Engagement | None:
        row = self._rows.get(entity_id)
        if row is not None and row.organization_id == organization_id:
            return row
        return None

    async def update_for_organization(
        self, entity: Engagement, *, organization_id: uuid.UUID
    ) -> Engagement:
        assert entity.id is not None
        existing = self._rows.get(entity.id)
        if existing is None or existing.organization_id != organization_id:
            raise NotFoundError(f"Engagement {entity.id} not found")
        self._rows[entity.id] = entity
        return entity

    async def create(self, entity: Engagement) -> Engagement:
        new_id = uuid.uuid4()
        created = Engagement(
            id=new_id,
            organization_id=entity.organization_id,
            title=entity.title,
            status=entity.status,
            created_at=datetime.now(timezone.utc),
        )
        self._rows[new_id] = created
        return created

    async def update(self, entity: Engagement) -> Engagement:
        assert entity.id is not None
        if entity.id not in self._rows:
            raise NotFoundError(f"Engagement {entity.id} not found")
        self._rows[entity.id] = entity
        return entity

    async def delete(self, entity: Engagement) -> None:
        if entity.id is not None:
            self._rows.pop(entity.id, None)


class FakeOrganizationRepository(IOrganizationRepository):
    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, Organization] = {}

    def seed(self, organization_id: uuid.UUID) -> None:
        self._rows[organization_id] = Organization(
            id=organization_id, name="Seed Org", created_at=datetime.now(timezone.utc)
        )

    async def get_for_organization(
        self, organization_id: uuid.UUID
    ) -> Organization | None:
        return self._rows.get(organization_id)

    async def create(self, entity: Organization) -> Organization:
        raise NotImplementedError

    async def update(self, entity: Organization) -> Organization:
        raise NotImplementedError

    async def delete(self, entity: Organization) -> None:
        raise NotImplementedError


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
def organization_repository() -> FakeOrganizationRepository:
    return FakeOrganizationRepository()


@pytest.fixture
def engagement_repository() -> FakeEngagementRepository:
    return FakeEngagementRepository()


@pytest.fixture
def service(
    engagement_repository: FakeEngagementRepository,
    organization_repository: FakeOrganizationRepository,
) -> EngagementService:
    return EngagementService(engagement_repository, organization_repository)


@pytest.fixture
def organization_a_id(organization_repository: FakeOrganizationRepository) -> uuid.UUID:
    org_id = uuid.uuid4()
    organization_repository.seed(org_id)
    return org_id


@pytest.fixture
def organization_b_id(organization_repository: FakeOrganizationRepository) -> uuid.UUID:
    org_id = uuid.uuid4()
    organization_repository.seed(org_id)
    return org_id


@pytest.fixture
def user_a(organization_a_id: uuid.UUID) -> User:
    return _user(organization_a_id)


@pytest.fixture
def user_b(organization_b_id: uuid.UUID) -> User:
    return _user(organization_b_id)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def test_create_in_own_organization_succeeds(
    service: EngagementService, user_a: User, organization_a_id: uuid.UUID
) -> None:
    created = await service.create(organization_a_id, "Audit 2026", "planning", user_a)

    assert created.id is not None
    assert created.organization_id == organization_a_id
    assert created.title == "Audit 2026"
    assert created.status == "planning"


async def test_create_in_another_organization_rejected_with_403(
    service: EngagementService, user_a: User, organization_b_id: uuid.UUID
) -> None:
    with pytest.raises(AuthorizationError):
        await service.create(organization_b_id, "Audit 2026", "planning", user_a)


async def test_create_with_null_user_organization_rejected_with_403(
    service: EngagementService, organization_a_id: uuid.UUID
) -> None:
    user = _user(None)
    with pytest.raises(AuthorizationError):
        await service.create(organization_a_id, "Audit 2026", "planning", user)


async def test_create_with_missing_organization_raises_not_found(
    service: EngagementService,
) -> None:
    user = _user(uuid.uuid4())
    with pytest.raises(NotFoundError):
        await service.create(user.organization_id, "Audit 2026", "planning", user)  # type: ignore[arg-type]


async def test_create_in_another_organization_does_not_persist_a_row(
    service: EngagementService,
    engagement_repository: FakeEngagementRepository,
    user_a: User,
    organization_b_id: uuid.UUID,
) -> None:
    with pytest.raises(AuthorizationError):
        await service.create(organization_b_id, "Audit 2026", "planning", user_a)

    assert await engagement_repository.count(organization_id=organization_b_id) == 0


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


async def test_get_own_engagement_succeeds(
    service: EngagementService,
    engagement_repository: FakeEngagementRepository,
    user_a: User,
    organization_a_id: uuid.UUID,
) -> None:
    engagement = engagement_repository.seed(organization_a_id)

    fetched = await service.get(engagement.id, user_a)  # type: ignore[arg-type]

    assert fetched.id == engagement.id


async def test_get_another_tenants_engagement_returns_not_found(
    service: EngagementService,
    engagement_repository: FakeEngagementRepository,
    user_a: User,
    organization_b_id: uuid.UUID,
) -> None:
    engagement = engagement_repository.seed(organization_b_id)

    with pytest.raises(NotFoundError):
        await service.get(engagement.id, user_a)  # type: ignore[arg-type]


async def test_get_missing_engagement_returns_identical_not_found(
    service: EngagementService, user_a: User
) -> None:
    with pytest.raises(NotFoundError):
        await service.get(uuid.uuid4(), user_a)


async def test_get_rejected_for_user_with_null_organization(
    service: EngagementService,
    engagement_repository: FakeEngagementRepository,
    organization_a_id: uuid.UUID,
) -> None:
    engagement = engagement_repository.seed(organization_a_id)
    user = _user(None)
    with pytest.raises(AuthorizationError):
        await service.get(engagement.id, user)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


async def test_list_automatically_scopes_to_own_organization(
    service: EngagementService,
    engagement_repository: FakeEngagementRepository,
    user_a: User,
    organization_a_id: uuid.UUID,
    organization_b_id: uuid.UUID,
) -> None:
    engagement_repository.seed(organization_a_id, "Engagement A")
    engagement_repository.seed(organization_b_id, "Engagement B")

    items, total = await service.list(user_a, page=1, page_size=20)

    assert total == 1
    assert len(items) == 1
    assert items[0].organization_id == organization_a_id


async def test_list_with_matching_organization_id_filter_succeeds(
    service: EngagementService,
    engagement_repository: FakeEngagementRepository,
    user_a: User,
    organization_a_id: uuid.UUID,
) -> None:
    engagement_repository.seed(organization_a_id)

    items, total = await service.list(
        user_a, page=1, page_size=20, organization_id=organization_a_id
    )

    assert total == 1
    assert len(items) == 1


async def test_list_with_foreign_organization_id_filter_rejected_with_403(
    service: EngagementService, user_a: User, organization_b_id: uuid.UUID
) -> None:
    with pytest.raises(AuthorizationError):
        await service.list(user_a, page=1, page_size=20, organization_id=organization_b_id)


async def test_list_rejected_for_user_with_null_organization(
    service: EngagementService,
) -> None:
    user = _user(None)
    with pytest.raises(AuthorizationError):
        await service.list(user, page=1, page_size=20)


async def test_list_empty_returns_no_items_and_zero_total(
    service: EngagementService, user_a: User
) -> None:
    items, total = await service.list(user_a, page=1, page_size=20)

    assert items == []
    assert total == 0


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


async def test_update_own_engagement_succeeds(
    service: EngagementService,
    engagement_repository: FakeEngagementRepository,
    user_a: User,
    organization_a_id: uuid.UUID,
) -> None:
    engagement = engagement_repository.seed(organization_a_id, "Old Title")

    updated = await service.update(
        engagement.id,  # type: ignore[arg-type]
        title="New Title",
        status=None,
        organization_id=None,
        current_user=user_a,
    )

    assert updated.title == "New Title"
    assert updated.status == "planning"  # unchanged
    assert updated.organization_id == organization_a_id  # unchanged


async def test_update_another_tenants_engagement_returns_not_found(
    service: EngagementService,
    engagement_repository: FakeEngagementRepository,
    user_a: User,
    organization_b_id: uuid.UUID,
) -> None:
    engagement = engagement_repository.seed(organization_b_id)

    with pytest.raises(NotFoundError):
        await service.update(
            engagement.id,  # type: ignore[arg-type]
            title="Hijacked",
            status=None,
            organization_id=None,
            current_user=user_a,
        )


async def test_update_does_not_change_another_tenants_engagement(
    service: EngagementService,
    engagement_repository: FakeEngagementRepository,
    user_a: User,
    organization_b_id: uuid.UUID,
) -> None:
    engagement = engagement_repository.seed(organization_b_id, "Original Title")

    with pytest.raises(NotFoundError):
        await service.update(
            engagement.id,  # type: ignore[arg-type]
            title="Hijacked",
            status=None,
            organization_id=None,
            current_user=user_a,
        )

    # Verified from the *owner's* scope: the repository no longer offers an
    # unscoped get (MVP Slice 3 closure), and reading Organization B's row
    # as Organization B is what "unchanged for its owner" actually means.
    untouched = await engagement_repository.get_for_organization(
        engagement.id, organization_id=organization_b_id  # type: ignore[arg-type]
    )
    assert untouched is not None
    assert untouched.title == "Original Title"


async def test_cross_tenant_reassignment_rejected_with_403(
    service: EngagementService,
    engagement_repository: FakeEngagementRepository,
    user_a: User,
    organization_a_id: uuid.UUID,
    organization_b_id: uuid.UUID,
) -> None:
    engagement = engagement_repository.seed(organization_a_id)

    with pytest.raises(AuthorizationError):
        await service.update(
            engagement.id,  # type: ignore[arg-type]
            title=None,
            status=None,
            organization_id=organization_b_id,
            current_user=user_a,
        )


async def test_cross_tenant_reassignment_does_not_change_the_row(
    service: EngagementService,
    engagement_repository: FakeEngagementRepository,
    user_a: User,
    organization_a_id: uuid.UUID,
    organization_b_id: uuid.UUID,
) -> None:
    engagement = engagement_repository.seed(organization_a_id)

    with pytest.raises(AuthorizationError):
        await service.update(
            engagement.id,  # type: ignore[arg-type]
            title=None,
            status=None,
            organization_id=organization_b_id,
            current_user=user_a,
        )

    untouched = await engagement_repository.get_for_organization(
        engagement.id, organization_id=organization_a_id  # type: ignore[arg-type]
    )
    assert untouched is not None
    assert untouched.organization_id == organization_a_id


async def test_supplied_same_organization_id_is_accepted_as_a_no_op(
    service: EngagementService,
    engagement_repository: FakeEngagementRepository,
    user_a: User,
    organization_a_id: uuid.UUID,
) -> None:
    engagement = engagement_repository.seed(organization_a_id)

    updated = await service.update(
        engagement.id,  # type: ignore[arg-type]
        title=None,
        status=None,
        organization_id=organization_a_id,
        current_user=user_a,
    )

    assert updated.organization_id == organization_a_id


async def test_update_rejected_for_user_with_null_organization(
    service: EngagementService,
    engagement_repository: FakeEngagementRepository,
    organization_a_id: uuid.UUID,
) -> None:
    engagement = engagement_repository.seed(organization_a_id)
    user = _user(None)
    with pytest.raises(AuthorizationError):
        await service.update(
            engagement.id,  # type: ignore[arg-type]
            title="New",
            status=None,
            organization_id=None,
            current_user=user,
        )


async def test_update_missing_engagement_returns_not_found(
    service: EngagementService, user_a: User
) -> None:
    with pytest.raises(NotFoundError):
        await service.update(
            uuid.uuid4(), title="New", status=None, organization_id=None, current_user=user_a
        )
