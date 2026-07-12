"""Integration API tests for Organization Management endpoints.

These exercise the endpoints through the real ``app`` (via the ``client``
fixture's in-process ``ASGITransport``), which resolves ``get_db`` to a real
``AsyncSessionLocal`` against the configured ``DATABASE_URL`` -- so every
test here actually creates/reads/updates rows in the real database. Every
row a test creates is tracked by id and deleted, via an independent
session, in ``cleanup_ids``'s teardown -- regardless of test outcome.

Marked ``integration`` module-wide, mirroring
``test_document_repository.py``, so the default CI run
(``pytest -m "not integration"``) skips this file entirely.
"""

import uuid
from typing import AsyncIterator

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.infrastructure.db.models.organization import Organization as OrganizationModel
from app.infrastructure.db.session import AsyncSessionLocal

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _require_database_url() -> None:
    if not get_settings().database_url:
        pytest.skip("integration tests require DATABASE_URL to be set")


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


async def test_create_organization_returns_201_and_persists(
    client: AsyncClient, cleanup_ids: list[uuid.UUID]
) -> None:
    response = await client.post("/api/v1/organizations", json={"name": "  Acme Corp  "})
    assert response.status_code == 201

    body = response.json()
    cleanup_ids.append(uuid.UUID(body["id"]))

    assert body["name"] == "Acme Corp"
    assert body["created_at"] is not None

    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(OrganizationModel, uuid.UUID(body["id"]))
        assert model is not None
        assert model.name == "Acme Corp"


async def test_get_existing_organization_returns_200(
    client: AsyncClient, cleanup_ids: list[uuid.UUID]
) -> None:
    created = await client.post("/api/v1/organizations", json={"name": "Beta Org"})
    organization_id = created.json()["id"]
    cleanup_ids.append(uuid.UUID(organization_id))

    response = await client.get(f"/api/v1/organizations/{organization_id}")

    assert response.status_code == 200
    assert response.json()["id"] == organization_id
    assert response.json()["name"] == "Beta Org"


async def test_get_missing_organization_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/organizations/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_list_returns_created_organizations_in_deterministic_order(
    client: AsyncClient, cleanup_ids: list[uuid.UUID]
) -> None:
    names = ["List Org A", "List Org B", "List Org C"]
    created_ids = []
    for name in names:
        response = await client.post("/api/v1/organizations", json={"name": name})
        created_ids.append(response.json()["id"])
    cleanup_ids.extend(uuid.UUID(cid) for cid in created_ids)

    response = await client.get("/api/v1/organizations", params={"page": 1, "page_size": 100})

    assert response.status_code == 200
    body = response.json()
    listed_ids = [item["id"] for item in body["items"]]
    positions = [listed_ids.index(cid) for cid in created_ids]
    assert positions == sorted(positions)  # created_ids appear in creation order


async def test_list_pagination_defaults_and_boundaries(
    client: AsyncClient, cleanup_ids: list[uuid.UUID]
) -> None:
    created_ids = []
    for i in range(3):
        response = await client.post(
            "/api/v1/organizations", json={"name": f"Page Org {i}"}
        )
        created_ids.append(response.json()["id"])
    cleanup_ids.extend(uuid.UUID(cid) for cid in created_ids)

    default_response = await client.get("/api/v1/organizations")
    assert default_response.status_code == 200
    assert default_response.json()["page"] == 1
    assert default_response.json()["page_size"] == 20

    page_response = await client.get(
        "/api/v1/organizations", params={"page": 1, "page_size": 1}
    )
    assert page_response.status_code == 200
    assert len(page_response.json()["items"]) == 1
    assert page_response.json()["total"] >= 3


async def test_update_organization_returns_200_and_persists_new_name(
    client: AsyncClient, cleanup_ids: list[uuid.UUID]
) -> None:
    created = await client.post("/api/v1/organizations", json={"name": "Old Name"})
    organization_id = created.json()["id"]
    cleanup_ids.append(uuid.UUID(organization_id))
    created_at = created.json()["created_at"]

    response = await client.patch(
        f"/api/v1/organizations/{organization_id}", json={"name": "New Name"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New Name"
    assert body["id"] == organization_id
    assert body["created_at"] == created_at  # created_at preserved


async def test_update_missing_organization_returns_404(client: AsyncClient) -> None:
    response = await client.patch(
        f"/api/v1/organizations/{uuid.uuid4()}", json={"name": "New Name"}
    )
    assert response.status_code == 404
