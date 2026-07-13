"""API-level tests for the Organization Management endpoints.

Uses FastAPI's ``dependency_overrides`` to substitute a test-controlled
Supabase JWT verifier, an in-memory fake user repository (reusing
``test_auth.py``'s fakes), and the real ``OrganizationService`` wired
with an in-memory fake ``IOrganizationRepository`` -- no network call to
Supabase, no database. This exercises the router's auth wiring together
with the service's tenant-isolation logic, since the latter is exactly
what this router previously lacked.
"""

import uuid
from datetime import datetime, timezone
from typing import Sequence

import pytest
from httpx import AsyncClient

from app.api.deps import get_organization_service, get_supabase_jwt_verifier, get_user_repository
from app.core.exceptions import NotFoundError
from app.domain.entities.organization import Organization
from app.domain.entities.user import User
from app.domain.repositories.organization import IOrganizationRepository
from app.main import app
from app.services.organization import OrganizationService

from tests.api.test_auth import FakeUserRepository, FakeVerifier


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

    async def get(self, entity_id: uuid.UUID) -> Organization | None:
        return self._rows.get(entity_id)

    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[Organization]:
        rows = sorted(self._rows.values(), key=lambda o: (o.created_at, str(o.id)))
        return rows[offset : offset + limit]

    async def count(self) -> int:
        return len(self._rows)

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


@pytest.fixture
def fake_repository() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def fake_verifier() -> FakeVerifier:
    return FakeVerifier()


@pytest.fixture
def fake_organization_repository() -> FakeOrganizationRepository:
    return FakeOrganizationRepository()


@pytest.fixture(autouse=True)
def _override_dependencies(
    fake_repository: FakeUserRepository,
    fake_verifier: FakeVerifier,
    fake_organization_repository: FakeOrganizationRepository,
):
    app.dependency_overrides[get_supabase_jwt_verifier] = lambda: fake_verifier
    app.dependency_overrides[get_user_repository] = lambda: fake_repository
    app.dependency_overrides[get_organization_service] = lambda: OrganizationService(
        fake_organization_repository
    )
    yield
    app.dependency_overrides.pop(get_supabase_jwt_verifier, None)
    app.dependency_overrides.pop(get_user_repository, None)
    app.dependency_overrides.pop(get_organization_service, None)


def _register_user(
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    *,
    token: str = "valid-token",
    organization_id: uuid.UUID | None,
) -> dict:
    user_id = uuid.uuid4()
    fake_verifier.register(token, user_id)
    fake_repository.seed(
        User(
            id=user_id,
            organization_id=organization_id,
            full_name="Test User",
            email="test@example.com",
            role=None,
            created_at=datetime.now(timezone.utc),
        )
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Unauthenticated / unprovisioned -- every route
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path_suffix",
    [
        ("post", ""),
        ("get", ""),
        ("get", "/{id}"),
        ("patch", "/{id}"),
    ],
)
async def test_unauthenticated_request_returns_401(
    client: AsyncClient, method: str, path_suffix: str
) -> None:
    path = "/api/v1/organizations" + path_suffix.format(id=uuid.uuid4())
    response = await client.request(method, path, json={"name": "Acme"} if method != "get" else None)
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


async def test_invalid_token_returns_401(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/organizations", headers={"Authorization": "Bearer not-a-registered-token"}
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


async def test_missing_profile_returns_403(
    client: AsyncClient, fake_verifier: FakeVerifier
) -> None:
    user_id = uuid.uuid4()
    fake_verifier.register("orphan-token", user_id)

    response = await client.get(
        "/api/v1/organizations", headers={"Authorization": "Bearer orphan-token"}
    )
    assert response.status_code == 403


async def test_null_organization_profile_returns_403_on_list(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _register_user(fake_verifier, fake_repository, organization_id=None)
    response = await client.get("/api/v1/organizations", headers=headers)
    assert response.status_code == 403


async def test_null_organization_profile_returns_403_on_get(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _register_user(fake_verifier, fake_repository, organization_id=None)
    response = await client.get(f"/api/v1/organizations/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 403


async def test_null_organization_profile_returns_403_on_update(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _register_user(fake_verifier, fake_repository, organization_id=None)
    response = await client.patch(
        f"/api/v1/organizations/{uuid.uuid4()}", headers=headers, json={"name": "Acme"}
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Create -- disabled
# ---------------------------------------------------------------------------


async def test_create_authenticated_returns_403(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
) -> None:
    headers = _register_user(fake_verifier, fake_repository, organization_id=uuid.uuid4())
    response = await client.post(
        "/api/v1/organizations", headers=headers, json={"name": "New Org"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Organization creation is not available in this phase."


# ---------------------------------------------------------------------------
# List -- own organization only
# ---------------------------------------------------------------------------


async def test_list_returns_only_own_organization(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    fake_organization_repository: FakeOrganizationRepository,
) -> None:
    own_org = fake_organization_repository.seed("My Org")
    fake_organization_repository.seed("Someone Else's Org")
    headers = _register_user(fake_verifier, fake_repository, organization_id=own_org.id)

    response = await client.get("/api/v1/organizations", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == str(own_org.id)
    assert set(body.keys()) == {"items", "page", "page_size", "total"}


# ---------------------------------------------------------------------------
# Get / Update -- own vs. other organization
# ---------------------------------------------------------------------------


async def test_get_own_organization_returns_200(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    fake_organization_repository: FakeOrganizationRepository,
) -> None:
    own_org = fake_organization_repository.seed("My Org")
    headers = _register_user(fake_verifier, fake_repository, organization_id=own_org.id)

    response = await client.get(f"/api/v1/organizations/{own_org.id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == str(own_org.id)


async def test_get_other_organization_returns_404(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    fake_organization_repository: FakeOrganizationRepository,
) -> None:
    own_org = fake_organization_repository.seed("My Org")
    other_org = fake_organization_repository.seed("Other Org")
    headers = _register_user(fake_verifier, fake_repository, organization_id=own_org.id)

    response = await client.get(f"/api/v1/organizations/{other_org.id}", headers=headers)

    assert response.status_code == 404


async def test_get_missing_organization_returns_identical_404(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    fake_organization_repository: FakeOrganizationRepository,
) -> None:
    own_org = fake_organization_repository.seed("My Org")
    other_org = fake_organization_repository.seed("Other Org")
    headers = _register_user(fake_verifier, fake_repository, organization_id=own_org.id)

    cross_tenant_response = await client.get(
        f"/api/v1/organizations/{other_org.id}", headers=headers
    )
    missing_response = await client.get(
        f"/api/v1/organizations/{uuid.uuid4()}", headers=headers
    )

    assert cross_tenant_response.status_code == missing_response.status_code == 404
    assert cross_tenant_response.json().keys() == missing_response.json().keys()


async def test_update_own_organization_returns_200(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    fake_organization_repository: FakeOrganizationRepository,
) -> None:
    own_org = fake_organization_repository.seed("My Org")
    headers = _register_user(fake_verifier, fake_repository, organization_id=own_org.id)

    response = await client.patch(
        f"/api/v1/organizations/{own_org.id}", headers=headers, json={"name": "Renamed"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"


async def test_update_other_organization_returns_404(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    fake_organization_repository: FakeOrganizationRepository,
) -> None:
    own_org = fake_organization_repository.seed("My Org")
    other_org = fake_organization_repository.seed("Other Org")
    headers = _register_user(fake_verifier, fake_repository, organization_id=own_org.id)

    response = await client.patch(
        f"/api/v1/organizations/{other_org.id}", headers=headers, json={"name": "Hijacked"}
    )

    assert response.status_code == 404
    assert fake_organization_repository._rows[other_org.id].name == "Other Org"  # untouched


async def test_update_invalid_uuid_returns_422(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _register_user(fake_verifier, fake_repository, organization_id=uuid.uuid4())
    response = await client.patch(
        "/api/v1/organizations/not-a-uuid", headers=headers, json={"name": "Acme"}
    )
    assert response.status_code == 422


async def test_update_blank_name_returns_422(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    fake_organization_repository: FakeOrganizationRepository,
) -> None:
    own_org = fake_organization_repository.seed("My Org")
    headers = _register_user(fake_verifier, fake_repository, organization_id=own_org.id)

    response = await client.patch(
        f"/api/v1/organizations/{own_org.id}", headers=headers, json={"name": "   "}
    )
    assert response.status_code == 422


async def test_get_invalid_uuid_returns_422(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _register_user(fake_verifier, fake_repository, organization_id=uuid.uuid4())
    response = await client.get("/api/v1/organizations/not-a-uuid", headers=headers)
    assert response.status_code == 422


async def test_list_page_below_minimum_returns_422(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _register_user(fake_verifier, fake_repository, organization_id=uuid.uuid4())
    response = await client.get(
        "/api/v1/organizations", headers=headers, params={"page": 0}
    )
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

    # Every operation must declare bearer-token security -- confirms the
    # authentication requirement is visible in the API contract, not
    # just enforced silently at runtime.
    for path_item in paths["/api/v1/organizations"].values():
        assert path_item.get("security"), "expected a security requirement on this operation"
    for path_item in paths["/api/v1/organizations/{organization_id}"].values():
        assert path_item.get("security"), "expected a security requirement on this operation"
