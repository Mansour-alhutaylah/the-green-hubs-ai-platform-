"""Unit tests for ``OrganizationService`` -- business logic exercised against
an in-memory fake repository. No database, no HTTP, no ``integration`` mark.
"""

import uuid
from datetime import datetime, timezone
from typing import Sequence

import pytest

from app.core.exceptions import NotFoundError
from app.domain.entities.organization import Organization
from app.domain.repositories.organization import IOrganizationRepository
from app.services.organization import OrganizationService


class FakeOrganizationRepository(IOrganizationRepository):
    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, Organization] = {}

    async def get(self, entity_id: uuid.UUID) -> Organization | None:
        return self._rows.get(entity_id)

    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[Organization]:
        rows = sorted(self._rows.values(), key=lambda o: (o.created_at, str(o.id)))
        return rows[offset : offset + limit]

    async def count(self) -> int:
        return len(self._rows)

    async def create(self, entity: Organization) -> Organization:
        new_id = uuid.uuid4()
        created = Organization(
            id=new_id, name=entity.name, created_at=datetime.now(timezone.utc)
        )
        self._rows[new_id] = created
        return created

    async def update(self, entity: Organization) -> Organization:
        assert entity.id is not None
        if entity.id not in self._rows:
            raise NotFoundError(f"Organization {entity.id} not found")
        self._rows[entity.id] = entity
        return entity

    async def delete(self, entity: Organization) -> None:
        if entity.id is not None:
            self._rows.pop(entity.id, None)


@pytest.fixture
def repository() -> FakeOrganizationRepository:
    return FakeOrganizationRepository()


@pytest.fixture
def service(repository: FakeOrganizationRepository) -> OrganizationService:
    return OrganizationService(repository)


async def test_create_persists_and_returns_organization(service: OrganizationService) -> None:
    created = await service.create("Acme Corp")

    assert created.id is not None
    assert created.name == "Acme Corp"
    assert created.created_at is not None


async def test_get_returns_existing_organization(service: OrganizationService) -> None:
    created = await service.create("Acme Corp")

    fetched = await service.get(created.id)  # type: ignore[arg-type]

    assert fetched.id == created.id
    assert fetched.name == "Acme Corp"


async def test_get_raises_not_found_for_missing_organization(
    service: OrganizationService,
) -> None:
    with pytest.raises(NotFoundError):
        await service.get(uuid.uuid4())


async def test_list_returns_all_items_and_total_when_under_page_size(
    service: OrganizationService,
) -> None:
    for name in ("Org A", "Org B", "Org C"):
        await service.create(name)

    items, total = await service.list(page=1, page_size=20)

    assert total == 3
    assert len(items) == 3


async def test_list_first_page_respects_page_size(service: OrganizationService) -> None:
    for name in ("Org A", "Org B", "Org C"):
        await service.create(name)

    items, total = await service.list(page=1, page_size=2)

    assert total == 3
    assert len(items) == 2


async def test_list_second_page_returns_remaining_items(service: OrganizationService) -> None:
    for name in ("Org A", "Org B", "Org C"):
        await service.create(name)

    items, total = await service.list(page=2, page_size=2)

    assert total == 3
    assert len(items) == 1


async def test_list_empty_returns_no_items_and_zero_total(
    service: OrganizationService,
) -> None:
    items, total = await service.list(page=1, page_size=20)

    assert items == []
    assert total == 0


async def test_update_changes_name_and_preserves_id_and_created_at(
    service: OrganizationService,
) -> None:
    created = await service.create("Old Name")

    updated = await service.update(created.id, "New Name")  # type: ignore[arg-type]

    assert updated.name == "New Name"
    assert updated.id == created.id
    assert updated.created_at == created.created_at


async def test_update_raises_not_found_for_missing_organization(
    service: OrganizationService,
) -> None:
    with pytest.raises(NotFoundError):
        await service.update(uuid.uuid4(), "New Name")
