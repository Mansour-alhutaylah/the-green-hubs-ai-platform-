"""Integration API tests for the authenticated-user profile endpoint.

Exercises the real verification path (a real ``SupabaseJWTVerifier`` built
from the actually-configured project settings) against a real, persisted
``public.users`` profile row -- without ever calling Supabase's Auth API or
creating any ``auth.users`` row. The test token is generated locally with a
throwaway EC keypair whose public key is injected as the JWKS response via
``dependency_overrides`` on ``get_supabase_jwt_verifier`` (only the JWKS
*source* is swapped for a local fake; the actual verification code path --
signature/claims/algorithm checks -- runs unmodified against a real,
persisted profile row and the project's real issuer/audience configuration).

No real Supabase Auth user is created or deleted. No production secret,
private key, or complete token is ever printed or logged. Every row a test
creates is tracked and deleted, via an independent session, in
``cleanup_ids``'s teardown -- profiles before organizations (dependency
-safe), regardless of test outcome.

Marked ``integration`` module-wide, mirroring
``test_organizations_integration.py``.
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
    """The project's actual issuer/audience, from the real, configured
    settings -- so tokens built against this fixture's ``issuer``/
    ``audience`` exercise the real verification contract."""
    return build_verifier_from_settings(get_settings())


@pytest.fixture(autouse=True)
def _override_verifier_jwks_source(keypair, real_verifier: SupabaseJWTVerifier):
    """Swaps only the JWKS *fetch* for a local fake -- never touching the
    real Supabase JWKS endpoint or requiring network access to Supabase
    for this test -- while keeping the real, configured issuer/audience."""
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


async def test_valid_token_resolves_a_real_profile_and_returns_safe_fields(
    client: AsyncClient,
    keypair,
    real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> None:
    private_key, _public_key = keypair

    async with AsyncSessionLocal() as session:
        organization = OrganizationModel(name="Auth Integration Test Org")
        session.add(organization)
        await session.flush()
        cleanup_ids["organizations"].append(organization.id)

        profile_id = uuid.uuid4()  # stands in for the corresponding auth.users id
        profile = UserModel(
            id=profile_id,
            organization_id=organization.id,
            full_name="Integration Test User",
            email="auth-integration-test@example.com",
            role="admin",
        )
        session.add(profile)
        await session.commit()
        cleanup_ids["users"].append(profile_id)

    token = _make_token(
        private_key,
        kid="integration-test-kid",
        overrides={
            "sub": str(profile_id),
            "iss": real_verifier.issuer,
            "aud": real_verifier.audience,
        },
    )

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(profile_id)
    assert body["organization_id"] == str(organization.id)
    assert body["full_name"] == "Integration Test User"
    assert body["email"] == "auth-integration-test@example.com"
    assert body["role"] == "admin"
    assert set(body.keys()) == {"id", "organization_id", "full_name", "email", "role"}


async def test_valid_token_with_no_matching_profile_returns_403(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier
) -> None:
    private_key, _public_key = keypair
    token = _make_token(
        private_key,
        kid="integration-test-kid",
        overrides={"iss": real_verifier.issuer, "aud": real_verifier.audience},
    )  # random, never-persisted sub

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
