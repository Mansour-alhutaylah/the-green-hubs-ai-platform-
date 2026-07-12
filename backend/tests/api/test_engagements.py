"""API-level validation tests for the Engagement Management endpoints.

None of these reach the repository/database -- every case here is rejected
by FastAPI/Pydantic request validation before the route handler runs, so
they are safe to run in the default (``not integration``) suite. Tests
that actually persist data live in ``test_engagements_integration.py``.
"""

import uuid

from httpx import AsyncClient


async def test_create_missing_organization_id_returns_422(client: AsyncClient) -> None:
    response = await client.post("/api/v1/engagements", json={"title": "Audit"})
    assert response.status_code == 422


async def test_create_null_organization_id_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/engagements", json={"organization_id": None, "title": "Audit"}
    )
    assert response.status_code == 422


async def test_create_malformed_organization_id_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/engagements", json={"organization_id": "not-a-uuid", "title": "Audit"}
    )
    assert response.status_code == 422


async def test_create_missing_title_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/engagements", json={"organization_id": str(uuid.uuid4())}
    )
    assert response.status_code == 422


async def test_create_blank_title_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/engagements", json={"organization_id": str(uuid.uuid4()), "title": ""}
    )
    assert response.status_code == 422


async def test_create_whitespace_only_title_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/engagements", json={"organization_id": str(uuid.uuid4()), "title": "   "}
    )
    assert response.status_code == 422


async def test_create_title_over_max_length_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/engagements",
        json={"organization_id": str(uuid.uuid4()), "title": "x" * 256},
    )
    assert response.status_code == 422


async def test_create_null_status_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/engagements",
        json={"organization_id": str(uuid.uuid4()), "title": "Audit", "status": None},
    )
    assert response.status_code == 422


async def test_create_blank_status_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/engagements",
        json={"organization_id": str(uuid.uuid4()), "title": "Audit", "status": ""},
    )
    assert response.status_code == 422


async def test_create_whitespace_only_status_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/engagements",
        json={"organization_id": str(uuid.uuid4()), "title": "Audit", "status": "   "},
    )
    assert response.status_code == 422


async def test_create_status_over_max_length_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/engagements",
        json={"organization_id": str(uuid.uuid4()), "title": "Audit", "status": "x" * 51},
    )
    assert response.status_code == 422


async def test_get_invalid_uuid_returns_422(client: AsyncClient) -> None:
    response = await client.get("/api/v1/engagements/not-a-uuid")
    assert response.status_code == 422


async def test_list_page_below_minimum_returns_422(client: AsyncClient) -> None:
    response = await client.get("/api/v1/engagements", params={"page": 0})
    assert response.status_code == 422


async def test_list_page_size_above_maximum_returns_422(client: AsyncClient) -> None:
    response = await client.get("/api/v1/engagements", params={"page_size": 101})
    assert response.status_code == 422


async def test_list_invalid_organization_id_filter_returns_422(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/engagements", params={"organization_id": "not-a-uuid"}
    )
    assert response.status_code == 422


async def test_update_empty_body_returns_422(client: AsyncClient) -> None:
    response = await client.patch(f"/api/v1/engagements/{uuid.uuid4()}", json={})
    assert response.status_code == 422


async def test_update_null_title_returns_422(client: AsyncClient) -> None:
    response = await client.patch(f"/api/v1/engagements/{uuid.uuid4()}", json={"title": None})
    assert response.status_code == 422


async def test_update_null_status_returns_422(client: AsyncClient) -> None:
    response = await client.patch(f"/api/v1/engagements/{uuid.uuid4()}", json={"status": None})
    assert response.status_code == 422


async def test_update_null_organization_id_returns_422(client: AsyncClient) -> None:
    response = await client.patch(
        f"/api/v1/engagements/{uuid.uuid4()}", json={"organization_id": None}
    )
    assert response.status_code == 422


async def test_update_blank_title_returns_422(client: AsyncClient) -> None:
    response = await client.patch(f"/api/v1/engagements/{uuid.uuid4()}", json={"title": ""})
    assert response.status_code == 422


async def test_update_whitespace_only_title_returns_422(client: AsyncClient) -> None:
    response = await client.patch(
        f"/api/v1/engagements/{uuid.uuid4()}", json={"title": "   "}
    )
    assert response.status_code == 422


async def test_update_blank_status_returns_422(client: AsyncClient) -> None:
    response = await client.patch(f"/api/v1/engagements/{uuid.uuid4()}", json={"status": ""})
    assert response.status_code == 422


async def test_update_whitespace_only_status_returns_422(client: AsyncClient) -> None:
    response = await client.patch(
        f"/api/v1/engagements/{uuid.uuid4()}", json={"status": "   "}
    )
    assert response.status_code == 422


async def test_update_title_over_max_length_returns_422(client: AsyncClient) -> None:
    response = await client.patch(
        f"/api/v1/engagements/{uuid.uuid4()}", json={"title": "x" * 256}
    )
    assert response.status_code == 422


async def test_update_status_over_max_length_returns_422(client: AsyncClient) -> None:
    response = await client.patch(
        f"/api/v1/engagements/{uuid.uuid4()}", json={"status": "x" * 51}
    )
    assert response.status_code == 422


async def test_update_invalid_uuid_returns_422(client: AsyncClient) -> None:
    response = await client.patch("/api/v1/engagements/not-a-uuid", json={"title": "Audit"})
    assert response.status_code == 422


async def test_update_malformed_organization_id_returns_422(client: AsyncClient) -> None:
    response = await client.patch(
        f"/api/v1/engagements/{uuid.uuid4()}", json={"organization_id": "not-a-uuid"}
    )
    assert response.status_code == 422


async def test_openapi_includes_engagement_paths(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]

    assert "/api/v1/engagements" in paths
    assert "post" in paths["/api/v1/engagements"]
    assert "get" in paths["/api/v1/engagements"]
    assert "/api/v1/engagements/{engagement_id}" in paths
    assert "get" in paths["/api/v1/engagements/{engagement_id}"]
    assert "patch" in paths["/api/v1/engagements/{engagement_id}"]
