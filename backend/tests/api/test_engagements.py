"""API-level tests for the Engagement Management endpoints.

Uses FastAPI's ``dependency_overrides`` to substitute a test-controlled
Supabase JWT verifier, an in-memory fake user repository (reusing
``test_auth.py``'s fakes), and the real ``EngagementService`` wired with
in-memory fake repositories -- no network call to Supabase, no database.
This exercises the router's auth wiring together with the service's
tenant-isolation logic, since the latter is exactly what this router
previously lacked.
"""

import uuid
from datetime import datetime, timezone
from typing import Sequence

import pytest
from httpx import AsyncClient

from app.api.deps import (
    get_engagement_service,
    get_supabase_jwt_verifier,
    get_user_repository,
)
from app.core.exceptions import NotFoundError
from app.domain.entities.engagement import Engagement
from app.domain.entities.organization import Organization
from app.domain.entities.user import User
from app.domain.repositories.engagement import IEngagementRepository
from app.domain.repositories.organization import IOrganizationRepository
from app.main import app
from app.services.engagement import EngagementService

from tests.api.test_auth import FakeUserRepository, FakeVerifier


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
        raise NotImplementedError

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
def fake_repository() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def fake_verifier() -> FakeVerifier:
    return FakeVerifier()


@pytest.fixture
def fake_engagement_repository() -> FakeEngagementRepository:
    return FakeEngagementRepository()


@pytest.fixture
def fake_organization_repository() -> FakeOrganizationRepository:
    return FakeOrganizationRepository()


@pytest.fixture(autouse=True)
def _override_dependencies(
    fake_repository: FakeUserRepository,
    fake_verifier: FakeVerifier,
    fake_engagement_repository: FakeEngagementRepository,
    fake_organization_repository: FakeOrganizationRepository,
):
    app.dependency_overrides[get_supabase_jwt_verifier] = lambda: fake_verifier
    app.dependency_overrides[get_user_repository] = lambda: fake_repository
    app.dependency_overrides[get_engagement_service] = lambda: EngagementService(
        fake_engagement_repository, fake_organization_repository
    )
    yield
    app.dependency_overrides.pop(get_supabase_jwt_verifier, None)
    app.dependency_overrides.pop(get_user_repository, None)
    app.dependency_overrides.pop(get_engagement_service, None)


def _register_user(
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    *,
    token: str = "valid-token",
    organization_id: uuid.UUID | None,
    role: str | None = "admin",
) -> dict:
    user_id = uuid.uuid4()
    fake_verifier.register(token, user_id)
    fake_repository.seed(
        User(
            id=user_id,
            organization_id=organization_id,
            full_name="Test User",
            email="test@example.com",
            # Write-capable by default so these tests still reach the
            # tenant/validation behaviour they exist to assert. Role-based
            # denial itself is covered in tests/api/test_authorization.py.
            role=role,
            created_at=datetime.now(timezone.utc),
        )
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def organization_a(fake_organization_repository: FakeOrganizationRepository) -> uuid.UUID:
    org_id = uuid.uuid4()
    fake_organization_repository.seed(org_id)
    return org_id


@pytest.fixture
def organization_b(fake_organization_repository: FakeOrganizationRepository) -> uuid.UUID:
    org_id = uuid.uuid4()
    fake_organization_repository.seed(org_id)
    return org_id


# ---------------------------------------------------------------------------
# Unauthenticated -- every route
# ---------------------------------------------------------------------------


async def test_unauthenticated_create_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/engagements", json={"organization_id": str(uuid.uuid4()), "title": "Audit"}
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


async def test_unauthenticated_list_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/engagements")
    assert response.status_code == 401


async def test_unauthenticated_get_returns_401(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/engagements/{uuid.uuid4()}")
    assert response.status_code == 401


async def test_unauthenticated_update_returns_401(client: AsyncClient) -> None:
    response = await client.patch(
        f"/api/v1/engagements/{uuid.uuid4()}", json={"title": "New"}
    )
    assert response.status_code == 401


async def test_invalid_token_returns_401(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/engagements", headers={"Authorization": "Bearer not-a-registered-token"}
    )
    assert response.status_code == 401


async def test_missing_profile_returns_403(
    client: AsyncClient, fake_verifier: FakeVerifier
) -> None:
    user_id = uuid.uuid4()
    fake_verifier.register("orphan-token", user_id)
    response = await client.get(
        "/api/v1/engagements", headers={"Authorization": "Bearer orphan-token"}
    )
    assert response.status_code == 403


async def test_null_organization_returns_403(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _register_user(fake_verifier, fake_repository, organization_id=None)
    response = await client.get("/api/v1/engagements", headers=headers)
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Own-tenant success
# ---------------------------------------------------------------------------


async def test_create_in_own_organization_returns_201(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    organization_a: uuid.UUID,
) -> None:
    headers = _register_user(fake_verifier, fake_repository, organization_id=organization_a)

    response = await client.post(
        "/api/v1/engagements",
        headers=headers,
        json={"organization_id": str(organization_a), "title": "Audit 2026"},
    )

    assert response.status_code == 201
    assert response.json()["organization_id"] == str(organization_a)


async def test_list_scoped_to_own_organization_returns_200(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    fake_engagement_repository: FakeEngagementRepository,
    organization_a: uuid.UUID,
    organization_b: uuid.UUID,
) -> None:
    fake_engagement_repository.seed(organization_a, "Mine")
    fake_engagement_repository.seed(organization_b, "Not Mine")
    headers = _register_user(fake_verifier, fake_repository, organization_id=organization_a)

    response = await client.get("/api/v1/engagements", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Mine"


async def test_get_own_engagement_returns_200(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    fake_engagement_repository: FakeEngagementRepository,
    organization_a: uuid.UUID,
) -> None:
    engagement = fake_engagement_repository.seed(organization_a)
    headers = _register_user(fake_verifier, fake_repository, organization_id=organization_a)

    response = await client.get(f"/api/v1/engagements/{engagement.id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == str(engagement.id)


async def test_update_own_engagement_returns_200(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    fake_engagement_repository: FakeEngagementRepository,
    organization_a: uuid.UUID,
) -> None:
    engagement = fake_engagement_repository.seed(organization_a, "Old Title")
    headers = _register_user(fake_verifier, fake_repository, organization_id=organization_a)

    response = await client.patch(
        f"/api/v1/engagements/{engagement.id}", headers=headers, json={"title": "New Title"}
    )

    assert response.status_code == 200
    assert response.json()["title"] == "New Title"


# ---------------------------------------------------------------------------
# Cross-tenant denial
# ---------------------------------------------------------------------------


async def test_create_in_another_organization_returns_403(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    organization_a: uuid.UUID,
    organization_b: uuid.UUID,
) -> None:
    headers = _register_user(fake_verifier, fake_repository, organization_id=organization_a)

    response = await client.post(
        "/api/v1/engagements",
        headers=headers,
        json={"organization_id": str(organization_b), "title": "Audit 2026"},
    )

    assert response.status_code == 403


async def test_list_with_foreign_organization_filter_returns_403(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    organization_a: uuid.UUID,
    organization_b: uuid.UUID,
) -> None:
    headers = _register_user(fake_verifier, fake_repository, organization_id=organization_a)

    response = await client.get(
        "/api/v1/engagements", headers=headers, params={"organization_id": str(organization_b)}
    )

    assert response.status_code == 403


async def test_get_another_tenants_engagement_returns_404(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    fake_engagement_repository: FakeEngagementRepository,
    organization_a: uuid.UUID,
    organization_b: uuid.UUID,
) -> None:
    engagement = fake_engagement_repository.seed(organization_b)
    headers = _register_user(fake_verifier, fake_repository, organization_id=organization_a)

    response = await client.get(f"/api/v1/engagements/{engagement.id}", headers=headers)

    assert response.status_code == 404


async def test_get_missing_and_cross_tenant_engagement_are_indistinguishable(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    fake_engagement_repository: FakeEngagementRepository,
    organization_a: uuid.UUID,
    organization_b: uuid.UUID,
) -> None:
    engagement = fake_engagement_repository.seed(organization_b)
    headers = _register_user(fake_verifier, fake_repository, organization_id=organization_a)

    cross_tenant_response = await client.get(
        f"/api/v1/engagements/{engagement.id}", headers=headers
    )
    missing_response = await client.get(
        f"/api/v1/engagements/{uuid.uuid4()}", headers=headers
    )

    assert cross_tenant_response.status_code == missing_response.status_code == 404
    assert cross_tenant_response.json().keys() == missing_response.json().keys()


async def test_update_another_tenants_engagement_returns_404(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    fake_engagement_repository: FakeEngagementRepository,
    organization_a: uuid.UUID,
    organization_b: uuid.UUID,
) -> None:
    engagement = fake_engagement_repository.seed(organization_b, "Original")
    headers = _register_user(fake_verifier, fake_repository, organization_id=organization_a)

    response = await client.patch(
        f"/api/v1/engagements/{engagement.id}", headers=headers, json={"title": "Hijacked"}
    )

    assert response.status_code == 404
    assert fake_engagement_repository._rows[engagement.id].title == "Original"  # untouched


async def test_cross_tenant_reassignment_returns_403(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    fake_engagement_repository: FakeEngagementRepository,
    organization_a: uuid.UUID,
    organization_b: uuid.UUID,
) -> None:
    engagement = fake_engagement_repository.seed(organization_a)
    headers = _register_user(fake_verifier, fake_repository, organization_id=organization_a)

    response = await client.patch(
        f"/api/v1/engagements/{engagement.id}",
        headers=headers,
        json={"organization_id": str(organization_b)},
    )

    assert response.status_code == 403
    assert fake_engagement_repository._rows[engagement.id].organization_id == organization_a


# ---------------------------------------------------------------------------
# Validation (unrelated to tenant scope)
# ---------------------------------------------------------------------------


async def test_create_missing_title_returns_422(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    organization_a: uuid.UUID,
) -> None:
    headers = _register_user(fake_verifier, fake_repository, organization_id=organization_a)
    response = await client.post(
        "/api/v1/engagements",
        headers=headers,
        json={"organization_id": str(organization_a)},
    )
    assert response.status_code == 422


async def test_update_empty_body_returns_422(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    fake_engagement_repository: FakeEngagementRepository,
    organization_a: uuid.UUID,
) -> None:
    engagement = fake_engagement_repository.seed(organization_a)
    headers = _register_user(fake_verifier, fake_repository, organization_id=organization_a)
    response = await client.patch(
        f"/api/v1/engagements/{engagement.id}", headers=headers, json={}
    )
    assert response.status_code == 422


async def test_openapi_includes_engagement_paths_with_security(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]

    assert "/api/v1/engagements" in paths
    assert "/api/v1/engagements/{engagement_id}" in paths
    for path_item in paths["/api/v1/engagements"].values():
        assert path_item.get("security")
    for path_item in paths["/api/v1/engagements/{engagement_id}"].values():
        assert path_item.get("security")
