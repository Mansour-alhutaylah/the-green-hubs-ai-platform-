"""Unit tests for ``EngagementService`` -- business logic exercised against
in-memory fake repositories. No database, no HTTP, no ``integration`` mark.
"""

import uuid
from datetime import datetime, timezone
from typing import Sequence

import pytest

from app.core.exceptions import NotFoundError
from app.domain.entities.engagement import Engagement
from app.domain.entities.organization import Organization
from app.domain.repositories.engagement import IEngagementRepository
from app.domain.repositories.organization import IOrganizationRepository
from app.services.engagement import EngagementService


class FakeEngagementRepository(IEngagementRepository):
    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, Engagement] = {}

    async def get(self, entity_id: uuid.UUID) -> Engagement | None:
        return self._rows.get(entity_id)

    async def list(
        self, *, limit: int = 100, offset: int = 0, organization_id: uuid.UUID | None = None
    ) -> Sequence[Engagement]:
        rows = [
            e
            for e in self._rows.values()
            if organization_id is None or e.organization_id == organization_id
        ]
        rows.sort(key=lambda e: (e.created_at, str(e.id)))
        return rows[offset : offset + limit]

    async def count(self, *, organization_id: uuid.UUID | None = None) -> int:
        return len(
            [
                e
                for e in self._rows.values()
                if organization_id is None or e.organization_id == organization_id
            ]
        )

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

    async def get(self, entity_id: uuid.UUID) -> Organization | None:
        return self._rows.get(entity_id)

    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[Organization]:
        return list(self._rows.values())[offset : offset + limit]

    async def count(self) -> int:
        return len(self._rows)

    async def create(self, entity: Organization) -> Organization:
        raise NotImplementedError

    async def update(self, entity: Organization) -> Organization:
        raise NotImplementedError

    async def delete(self, entity: Organization) -> None:
        raise NotImplementedError


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
def organization_id(organization_repository: FakeOrganizationRepository) -> uuid.UUID:
    org_id = uuid.uuid4()
    organization_repository.seed(org_id)
    return org_id


async def test_create_with_valid_organization_persists_engagement(
    service: EngagementService, organization_id: uuid.UUID
) -> None:
    created = await service.create(organization_id, "Audit 2026", "planning")

    assert created.id is not None
    assert created.organization_id == organization_id
    assert created.title == "Audit 2026"
    assert created.status == "planning"


async def test_create_with_missing_organization_raises_not_found(
    service: EngagementService,
) -> None:
    with pytest.raises(NotFoundError):
        await service.create(uuid.uuid4(), "Audit 2026", "planning")


async def test_get_returns_existing_engagement(
    service: EngagementService, organization_id: uuid.UUID
) -> None:
    created = await service.create(organization_id, "Audit 2026", "planning")

    fetched = await service.get(created.id)  # type: ignore[arg-type]

    assert fetched.id == created.id


async def test_get_raises_not_found_for_missing_engagement(
    service: EngagementService,
) -> None:
    with pytest.raises(NotFoundError):
        await service.get(uuid.uuid4())


async def test_list_filters_by_organization_id(
    service: EngagementService,
    organization_repository: FakeOrganizationRepository,
) -> None:
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    organization_repository.seed(org_a)
    organization_repository.seed(org_b)
    await service.create(org_a, "Engagement A", "planning")
    await service.create(org_b, "Engagement B", "planning")

    items, total = await service.list(page=1, page_size=20, organization_id=org_a)

    assert total == 1
    assert len(items) == 1
    assert items[0].organization_id == org_a


async def test_list_without_filter_returns_all(
    service: EngagementService, organization_id: uuid.UUID
) -> None:
    await service.create(organization_id, "Engagement A", "planning")
    await service.create(organization_id, "Engagement B", "planning")

    items, total = await service.list(page=1, page_size=20)

    assert total == 2
    assert len(items) == 2


async def test_list_empty_returns_no_items_and_zero_total(
    service: EngagementService,
) -> None:
    items, total = await service.list(page=1, page_size=20)

    assert items == []
    assert total == 0


async def test_update_changes_only_provided_fields(
    service: EngagementService, organization_id: uuid.UUID
) -> None:
    created = await service.create(organization_id, "Old Title", "planning")

    updated = await service.update(
        created.id,  # type: ignore[arg-type]
        title="New Title",
        status=None,
        organization_id=None,
    )

    assert updated.title == "New Title"
    assert updated.status == "planning"  # unchanged
    assert updated.organization_id == organization_id  # unchanged
    assert updated.created_at == created.created_at


async def test_update_with_new_valid_organization_succeeds(
    service: EngagementService,
    organization_repository: FakeOrganizationRepository,
    organization_id: uuid.UUID,
) -> None:
    other_org = uuid.uuid4()
    organization_repository.seed(other_org)
    created = await service.create(organization_id, "Title", "planning")

    updated = await service.update(
        created.id,  # type: ignore[arg-type]
        title=None,
        status=None,
        organization_id=other_org,
    )

    assert updated.organization_id == other_org


async def test_update_with_missing_organization_raises_not_found(
    service: EngagementService, organization_id: uuid.UUID
) -> None:
    created = await service.create(organization_id, "Title", "planning")

    with pytest.raises(NotFoundError):
        await service.update(
            created.id,  # type: ignore[arg-type]
            title=None,
            status=None,
            organization_id=uuid.uuid4(),
        )


async def test_update_raises_not_found_for_missing_engagement(
    service: EngagementService,
) -> None:
    with pytest.raises(NotFoundError):
        await service.update(uuid.uuid4(), title="New", status=None, organization_id=None)
