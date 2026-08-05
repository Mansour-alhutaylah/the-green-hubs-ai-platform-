"""Integration API tests for Organization Management endpoints.

Sprint 3.5.1 (Tenant Isolation & API Security) rewrite: these endpoints
now require authentication and enforce tenant scope, so every test here
uses the real orchestration path -- a real ``OrganizationService`` wired
with the real ``IOrganizationRepository`` against the configured
database -- authenticated via the same locally-signed-token technique as
``test_auth_integration.py``/``test_documents_integration.py``: the real
issuer/audience (from actual settings) with only the JWKS *fetch* faked,
never touching Supabase's Auth API, never creating any ``auth.users``
row.

Every row a test creates -- an Organization and a matching ``public.users``
profile -- is tracked and deleted, via an independent session, in
``cleanup_ids``'s teardown (users before organizations, since
``users.organization_id`` references ``organizations.id``), regardless
of test outcome. Two Organizations and two Users are used throughout to
exercise same-tenant success and cross-tenant denial.

Marked ``integration`` module-wide, mirroring
``test_document_processing_integration.py``.
"""

import uuid
from typing import AsyncIterator

import pytest
from httpx import AsyncClient

from app.api.deps import get_supabase_jwt_verifier
from app.core.config import get_settings
from app.infrastructure.db.models.organization import Organization as OrganizationModel
from app.infrastructure.db.models.user import User as UserModel
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.security.supabase_jwt import (
    JWKSCache,
    SupabaseJWTVerifier,
    build_verifier_from_settings,
)
from app.main import app

from tests.infrastructure.security.test_supabase_jwt import (
    _generate_keypair,
    _make_token,
    _public_key_to_jwk,
)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _require_database_url() -> None:
    if not get_settings().database_url:
        pytest.skip("integration tests require DATABASE_URL to be set")


@pytest.fixture
def keypair():
    return _generate_keypair()


@pytest.fixture
def real_verifier() -> SupabaseJWTVerifier:
    return build_verifier_from_settings(get_settings())


@pytest.fixture(autouse=True)
def _override_dependencies(keypair, real_verifier: SupabaseJWTVerifier):
    _private_key, public_key = keypair
    jwk = _public_key_to_jwk(public_key, "integration-test-kid")

    def fake_fetch(_uri: str) -> dict:
        return {"keys": [jwk]}

    test_verifier = SupabaseJWTVerifier(
        jwks_cache=JWKSCache(real_verifier.jwks_cache.jwks_uri, fetch=fake_fetch),
        issuer=real_verifier.issuer,
        audience=real_verifier.audience,
    )
    app.dependency_overrides[get_supabase_jwt_verifier] = lambda: test_verifier
    yield
    app.dependency_overrides.pop(get_supabase_jwt_verifier, None)


@pytest.fixture
async def cleanup_ids() -> AsyncIterator[dict[str, list[uuid.UUID]]]:
    ids: dict[str, list[uuid.UUID]] = {"users": [], "organizations": []}
    yield ids
    async with AsyncSessionLocal() as cleanup_session:
        for user_id in ids["users"]:
            model = await cleanup_session.get(UserModel, user_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for organization_id in ids["organizations"]:
            model = await cleanup_session.get(OrganizationModel, organization_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()


async def _make_organization_and_profile(
    cleanup_ids: dict[str, list[uuid.UUID]], *, name: str
) -> tuple[uuid.UUID, uuid.UUID]:
    async with AsyncSessionLocal() as session:
        organization = OrganizationModel(name=name)
        session.add(organization)
        await session.flush()
        cleanup_ids["organizations"].append(organization.id)

        profile_id = uuid.uuid4()
        profile = UserModel(
            id=profile_id,
            organization_id=organization.id,
            full_name="Organization Integration Test User",
            email=f"org-integration-{profile_id}@example.com",
            # Write-capable so these tests still reach the tenant behaviour
            # they assert; role denial is covered in tests/api/test_authorization.py.
            role="admin",
        )
        session.add(profile)
        await session.commit()
        cleanup_ids["users"].append(profile_id)

        return organization.id, profile_id


def _token_for(private_key, real_verifier: SupabaseJWTVerifier, profile_id: uuid.UUID) -> str:
    return _make_token(
        private_key,
        kid="integration-test-kid",
        overrides={
            "sub": str(profile_id),
            "iss": real_verifier.issuer,
            "aud": real_verifier.audience,
        },
    )


async def test_no_anonymous_success_remains_on_any_route(
    client: AsyncClient, cleanup_ids: dict[str, list[uuid.UUID]]
) -> None:
    organization_id, _profile_id = await _make_organization_and_profile(
        cleanup_ids, name="Anonymous Access Test Org"
    )

    assert (await client.post("/api/v1/organizations", json={"name": "X"})).status_code == 401
    assert (await client.get("/api/v1/organizations")).status_code == 401
    assert (
        await client.get(f"/api/v1/organizations/{organization_id}")
    ).status_code == 401
    assert (
        await client.patch(f"/api/v1/organizations/{organization_id}", json={"name": "X"})
    ).status_code == 401


async def test_user_a_sees_only_organization_a_when_listing(
    client: AsyncClient,
    keypair,
    real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> None:
    private_key, _public_key = keypair
    organization_a, profile_a = await _make_organization_and_profile(
        cleanup_ids, name="Organization A"
    )
    _organization_b, _profile_b = await _make_organization_and_profile(
        cleanup_ids, name="Organization B"
    )
    token = _token_for(private_key, real_verifier, profile_a)

    response = await client.get(
        "/api/v1/organizations", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == str(organization_a)


async def test_user_a_cannot_get_organization_b(
    client: AsyncClient,
    keypair,
    real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> None:
    private_key, _public_key = keypair
    _organization_a, profile_a = await _make_organization_and_profile(
        cleanup_ids, name="Organization A"
    )
    organization_b, _profile_b = await _make_organization_and_profile(
        cleanup_ids, name="Organization B"
    )
    token = _token_for(private_key, real_verifier, profile_a)

    response = await client.get(
        f"/api/v1/organizations/{organization_b}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


async def test_user_a_cannot_update_organization_b(
    client: AsyncClient,
    keypair,
    real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> None:
    private_key, _public_key = keypair
    _organization_a, profile_a = await _make_organization_and_profile(
        cleanup_ids, name="Organization A"
    )
    organization_b, _profile_b = await _make_organization_and_profile(
        cleanup_ids, name="Organization B"
    )
    token = _token_for(private_key, real_verifier, profile_a)

    response = await client.patch(
        f"/api/v1/organizations/{organization_b}",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Hijacked"},
    )

    assert response.status_code == 404

    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(OrganizationModel, organization_b)
        assert model is not None
        assert model.name == "Organization B"  # untouched


async def test_same_tenant_get_and_update_still_succeed(
    client: AsyncClient,
    keypair,
    real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> None:
    private_key, _public_key = keypair
    organization_a, profile_a = await _make_organization_and_profile(
        cleanup_ids, name="Organization A"
    )
    token = _token_for(private_key, real_verifier, profile_a)
    headers = {"Authorization": f"Bearer {token}"}

    get_response = await client.get(f"/api/v1/organizations/{organization_a}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == str(organization_a)

    update_response = await client.patch(
        f"/api/v1/organizations/{organization_a}", headers=headers, json={"name": "Renamed A"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Renamed A"

    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(OrganizationModel, organization_a)
        assert model is not None
        assert model.name == "Renamed A"


async def test_organization_creation_disabled_for_authenticated_user(
    client: AsyncClient,
    keypair,
    real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> None:
    private_key, _public_key = keypair
    _organization_id, profile_id = await _make_organization_and_profile(
        cleanup_ids, name="Creation Attempt Test Org"
    )
    token = _token_for(private_key, real_verifier, profile_id)

    response = await client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Should Never Exist"},
    )

    assert response.status_code == 403

    async with AsyncSessionLocal() as verify_session:
        from sqlalchemy import select

        result = await verify_session.execute(
            select(OrganizationModel).where(OrganizationModel.name == "Should Never Exist")
        )
        assert result.scalars().all() == []
