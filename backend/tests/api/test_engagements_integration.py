"""Integration API tests for Engagement Management endpoints.

Sprint 3.5.1 (Tenant Isolation & API Security) rewrite: these endpoints
now require authentication and enforce tenant scope, so every test here
uses the real orchestration path -- a real ``EngagementService`` wired
with the real ``IEngagementRepository``/``IOrganizationRepository``
against the configured database -- authenticated via the same
locally-signed-token technique as
``test_document_processing_integration.py``.

Two Organizations and two Users (one per organization) are created for
every cross-tenant test. Every row a test creates is tracked and deleted,
via an independent session, in ``cleanup_ids``'s teardown, in
dependency-safe order: engagements, then users, then organizations,
regardless of test outcome.

Marked ``integration`` module-wide, mirroring
``test_organizations_integration.py``.
"""

import uuid
from typing import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.deps import get_supabase_jwt_verifier
from app.core.config import get_settings
from app.infrastructure.db.models.engagement import Engagement as EngagementModel
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
    ids: dict[str, list[uuid.UUID]] = {"engagements": [], "users": [], "organizations": []}
    yield ids
    async with AsyncSessionLocal() as cleanup_session:
        for engagement_id in ids["engagements"]:
            model = await cleanup_session.get(EngagementModel, engagement_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
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
            full_name="Engagement Integration Test User",
            email=f"engagement-integration-{profile_id}@example.com",
            # Write-capable so these tests still reach the tenant behaviour
            # they assert; role denial is covered in tests/api/test_authorization.py.
            role="admin",
        )
        session.add(profile)
        await session.commit()
        cleanup_ids["users"].append(profile_id)

        return organization.id, profile_id


async def _make_engagement(
    cleanup_ids: dict[str, list[uuid.UUID]], organization_id: uuid.UUID, *, title: str
) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        engagement = EngagementModel(organization_id=organization_id, title=title)
        session.add(engagement)
        await session.commit()
        await session.refresh(engagement)
    cleanup_ids["engagements"].append(engagement.id)
    return engagement.id


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


async def test_user_a_never_receives_organization_b_engagements(
    client: AsyncClient,
    keypair,
    real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> None:
    private_key, _public_key = keypair
    organization_a, profile_a = await _make_organization_and_profile(
        cleanup_ids, name="Organization A"
    )
    organization_b, _profile_b = await _make_organization_and_profile(
        cleanup_ids, name="Organization B"
    )
    await _make_engagement(cleanup_ids, organization_a, title="Mine")
    await _make_engagement(cleanup_ids, organization_b, title="Not Mine")
    token = _token_for(private_key, real_verifier, profile_a)

    response = await client.get(
        "/api/v1/engagements", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1  # list total reflects only tenant-visible rows
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Mine"
    assert all(item["organization_id"] == str(organization_a) for item in body["items"])


async def test_user_a_cannot_read_user_bs_engagement(
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
    engagement_b = await _make_engagement(cleanup_ids, organization_b, title="B's Engagement")
    token = _token_for(private_key, real_verifier, profile_a)

    response = await client.get(
        f"/api/v1/engagements/{engagement_b}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


async def test_user_a_cannot_update_user_bs_engagement(
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
    engagement_b = await _make_engagement(cleanup_ids, organization_b, title="Original")
    token = _token_for(private_key, real_verifier, profile_a)

    response = await client.patch(
        f"/api/v1/engagements/{engagement_b}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Hijacked"},
    )

    assert response.status_code == 404

    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(EngagementModel, engagement_b)
        assert model is not None
        assert model.title == "Original"  # untouched


async def test_user_a_cannot_create_under_organization_b(
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

    response = await client.post(
        "/api/v1/engagements",
        headers={"Authorization": f"Bearer {token}"},
        json={"organization_id": str(organization_b), "title": "Should Never Exist"},
    )

    assert response.status_code == 403

    async with AsyncSessionLocal() as verify_session:
        result = await verify_session.execute(
            select(EngagementModel).where(EngagementModel.title == "Should Never Exist")
        )
        assert result.scalars().all() == []


async def test_user_a_cannot_reassign_across_tenants(
    client: AsyncClient,
    keypair,
    real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> None:
    private_key, _public_key = keypair
    organization_a, profile_a = await _make_organization_and_profile(
        cleanup_ids, name="Organization A"
    )
    organization_b, _profile_b = await _make_organization_and_profile(
        cleanup_ids, name="Organization B"
    )
    engagement_a = await _make_engagement(cleanup_ids, organization_a, title="Mine")
    token = _token_for(private_key, real_verifier, profile_a)

    response = await client.patch(
        f"/api/v1/engagements/{engagement_a}",
        headers={"Authorization": f"Bearer {token}"},
        json={"organization_id": str(organization_b)},
    )

    assert response.status_code == 403

    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(EngagementModel, engagement_a)
        assert model is not None
        assert model.organization_id == organization_a  # never reassigned


async def test_valid_same_tenant_operations_still_work(
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

    create_response = await client.post(
        "/api/v1/engagements",
        headers=headers,
        json={"organization_id": str(organization_a), "title": "Same Tenant Engagement"},
    )
    assert create_response.status_code == 201
    engagement_id = create_response.json()["id"]
    cleanup_ids["engagements"].append(uuid.UUID(engagement_id))

    get_response = await client.get(f"/api/v1/engagements/{engagement_id}", headers=headers)
    assert get_response.status_code == 200

    update_response = await client.patch(
        f"/api/v1/engagements/{engagement_id}", headers=headers, json={"title": "Updated Title"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Updated Title"

    list_response = await client.get("/api/v1/engagements", headers=headers)
    assert list_response.status_code == 200
    assert any(item["id"] == engagement_id for item in list_response.json()["items"])
