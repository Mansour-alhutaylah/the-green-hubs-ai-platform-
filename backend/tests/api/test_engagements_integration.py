"""Integration API tests for Engagement Management endpoints.

Exercises the endpoints through the real ``app`` (via the ``client``
fixture's in-process ``ASGITransport``), which resolves ``get_db`` to a
real ``AsyncSessionLocal`` against the configured ``DATABASE_URL``. Every
row a test creates -- an Engagement and, via ``make_organization``, an
Organization -- is tracked and deleted, via an independent session, in
``cleanup_ids``'s teardown, engagements before organizations (dependency
-safe: an Organization with a linked Engagement blocks deletion under
this schema's ``NO ACTION`` foreign key), regardless of test outcome.

Marked ``integration`` module-wide, mirroring
``test_organizations_integration.py``.
"""

import uuid
from typing import AsyncIterator, Awaitable, Callable

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.infrastructure.db.models.engagement import Engagement as EngagementModel
from app.infrastructure.db.models.organization import Organization as OrganizationModel
from app.infrastructure.db.session import AsyncSessionLocal

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _require_database_url() -> None:
    if not get_settings().database_url:
        pytest.skip("integration tests require DATABASE_URL to be set")


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
            model = OrganizationModel(name="Engagement API Test Org")
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


async def test_create_engagement_with_valid_organization_returns_201(
    client: AsyncClient, cleanup_ids: dict[str, list[uuid.UUID]], organization_id: uuid.UUID
) -> None:
    response = await client.post(
        "/api/v1/engagements",
        json={"organization_id": str(organization_id), "title": "Audit 2026"},
    )
    assert response.status_code == 201

    body = response.json()
    cleanup_ids["engagements"].append(uuid.UUID(body["id"]))

    assert body["organization_id"] == str(organization_id)
    assert body["title"] == "Audit 2026"
    assert body["status"] == "planning"  # default applied
    assert body["created_at"] is not None


async def test_create_engagement_with_missing_organization_returns_404(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/engagements",
        json={"organization_id": str(uuid.uuid4()), "title": "Audit 2026"},
    )
    assert response.status_code == 404


async def test_get_existing_engagement_returns_200(
    client: AsyncClient, cleanup_ids: dict[str, list[uuid.UUID]], organization_id: uuid.UUID
) -> None:
    created = await client.post(
        "/api/v1/engagements",
        json={"organization_id": str(organization_id), "title": "Get Engagement"},
    )
    engagement_id = created.json()["id"]
    cleanup_ids["engagements"].append(uuid.UUID(engagement_id))

    response = await client.get(f"/api/v1/engagements/{engagement_id}")

    assert response.status_code == 200
    assert response.json()["id"] == engagement_id


async def test_get_missing_engagement_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/engagements/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_list_returns_empty_items_for_unused_organization_filter(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/engagements", params={"organization_id": str(uuid.uuid4())}
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_list_filters_by_organization_id(
    client: AsyncClient,
    cleanup_ids: dict[str, list[uuid.UUID]],
    make_organization: Callable[[], Awaitable[uuid.UUID]],
) -> None:
    org_a = await make_organization()
    org_b = await make_organization()

    resp_a = await client.post(
        "/api/v1/engagements", json={"organization_id": str(org_a), "title": "Org A Engagement"}
    )
    resp_b = await client.post(
        "/api/v1/engagements", json={"organization_id": str(org_b), "title": "Org B Engagement"}
    )
    cleanup_ids["engagements"].extend(
        [uuid.UUID(resp_a.json()["id"]), uuid.UUID(resp_b.json()["id"])]
    )

    response = await client.get("/api/v1/engagements", params={"organization_id": str(org_a)})

    assert response.status_code == 200
    body = response.json()
    listed_ids = [item["id"] for item in body["items"]]
    assert all(item["organization_id"] == str(org_a) for item in body["items"])
    assert resp_a.json()["id"] in listed_ids
    assert resp_b.json()["id"] not in listed_ids


async def test_list_pagination_defaults(
    client: AsyncClient, cleanup_ids: dict[str, list[uuid.UUID]], organization_id: uuid.UUID
) -> None:
    response = await client.post(
        "/api/v1/engagements",
        json={"organization_id": str(organization_id), "title": "Pagination Engagement"},
    )
    cleanup_ids["engagements"].append(uuid.UUID(response.json()["id"]))

    list_response = await client.get("/api/v1/engagements")
    assert list_response.status_code == 200
    assert list_response.json()["page"] == 1
    assert list_response.json()["page_size"] == 20


async def test_update_engagement_title_only_leaves_other_fields_unchanged(
    client: AsyncClient, cleanup_ids: dict[str, list[uuid.UUID]], organization_id: uuid.UUID
) -> None:
    created = await client.post(
        "/api/v1/engagements",
        json={
            "organization_id": str(organization_id),
            "title": "Old Title",
            "status": "planning",
        },
    )
    engagement_id = created.json()["id"]
    cleanup_ids["engagements"].append(uuid.UUID(engagement_id))
    created_at = created.json()["created_at"]

    response = await client.patch(
        f"/api/v1/engagements/{engagement_id}", json={"title": "New Title"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New Title"
    assert body["status"] == "planning"  # unchanged
    assert body["organization_id"] == str(organization_id)  # unchanged
    assert body["created_at"] == created_at  # unchanged


async def test_update_engagement_organization_id_to_valid_new_organization(
    client: AsyncClient,
    cleanup_ids: dict[str, list[uuid.UUID]],
    make_organization: Callable[[], Awaitable[uuid.UUID]],
    organization_id: uuid.UUID,
) -> None:
    other_org = await make_organization()
    created = await client.post(
        "/api/v1/engagements",
        json={"organization_id": str(organization_id), "title": "Reassign Engagement"},
    )
    engagement_id = created.json()["id"]
    cleanup_ids["engagements"].append(uuid.UUID(engagement_id))

    response = await client.patch(
        f"/api/v1/engagements/{engagement_id}", json={"organization_id": str(other_org)}
    )

    assert response.status_code == 200
    assert response.json()["organization_id"] == str(other_org)


async def test_update_engagement_with_missing_organization_returns_404(
    client: AsyncClient, cleanup_ids: dict[str, list[uuid.UUID]], organization_id: uuid.UUID
) -> None:
    created = await client.post(
        "/api/v1/engagements",
        json={"organization_id": str(organization_id), "title": "Engagement"},
    )
    engagement_id = created.json()["id"]
    cleanup_ids["engagements"].append(uuid.UUID(engagement_id))

    response = await client.patch(
        f"/api/v1/engagements/{engagement_id}", json={"organization_id": str(uuid.uuid4())}
    )

    assert response.status_code == 404


async def test_update_missing_engagement_returns_404(client: AsyncClient) -> None:
    response = await client.patch(
        f"/api/v1/engagements/{uuid.uuid4()}", json={"title": "New Title"}
    )
    assert response.status_code == 404
