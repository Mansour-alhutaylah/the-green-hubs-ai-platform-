"""API-level validation tests for the Organization Management endpoints.

None of these reach the repository/database -- every case here is rejected
by FastAPI/Pydantic request validation before the route handler runs, so
they are safe to run in the default (``not integration``) suite. Tests that
actually persist data live in ``test_organizations_integration.py``.
"""

import uuid

from httpx import AsyncClient


async def test_create_missing_name_returns_422(client: AsyncClient) -> None:
    response = await client.post("/api/v1/organizations", json={})
    assert response.status_code == 422


async def test_create_null_name_returns_422(client: AsyncClient) -> None:
    response = await client.post("/api/v1/organizations", json={"name": None})
    assert response.status_code == 422


async def test_create_blank_name_returns_422(client: AsyncClient) -> None:
    response = await client.post("/api/v1/organizations", json={"name": ""})
    assert response.status_code == 422


async def test_create_whitespace_only_name_returns_422(client: AsyncClient) -> None:
    response = await client.post("/api/v1/organizations", json={"name": "   "})
    assert response.status_code == 422


async def test_get_invalid_uuid_returns_422(client: AsyncClient) -> None:
    response = await client.get("/api/v1/organizations/not-a-uuid")
    assert response.status_code == 422


async def test_update_empty_body_returns_422(client: AsyncClient) -> None:
    response = await client.patch(f"/api/v1/organizations/{uuid.uuid4()}", json={})
    assert response.status_code == 422


async def test_update_null_name_returns_422(client: AsyncClient) -> None:
    response = await client.patch(
        f"/api/v1/organizations/{uuid.uuid4()}", json={"name": None}
    )
    assert response.status_code == 422


async def test_update_blank_name_returns_422(client: AsyncClient) -> None:
    response = await client.patch(f"/api/v1/organizations/{uuid.uuid4()}", json={"name": ""})
    assert response.status_code == 422


async def test_update_whitespace_only_name_returns_422(client: AsyncClient) -> None:
    response = await client.patch(
        f"/api/v1/organizations/{uuid.uuid4()}", json={"name": "   "}
    )
    assert response.status_code == 422


async def test_update_invalid_uuid_returns_422(client: AsyncClient) -> None:
    response = await client.patch("/api/v1/organizations/not-a-uuid", json={"name": "Acme"})
    assert response.status_code == 422


async def test_list_page_below_minimum_returns_422(client: AsyncClient) -> None:
    response = await client.get("/api/v1/organizations", params={"page": 0})
    assert response.status_code == 422


async def test_list_page_size_above_maximum_returns_422(client: AsyncClient) -> None:
    response = await client.get("/api/v1/organizations", params={"page_size": 101})
    assert response.status_code == 422


async def test_openapi_includes_organization_paths(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]

    assert "/api/v1/organizations" in paths
    assert "post" in paths["/api/v1/organizations"]
    assert "get" in paths["/api/v1/organizations"]
    assert "/api/v1/organizations/{organization_id}" in paths
    assert "get" in paths["/api/v1/organizations/{organization_id}"]
    assert "patch" in paths["/api/v1/organizations/{organization_id}"]
