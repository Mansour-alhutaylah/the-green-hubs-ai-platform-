"""API-level tests for the authenticated-user profile endpoint.

Uses FastAPI's ``dependency_overrides`` to substitute a test-controlled
Supabase JWT verifier and an in-memory fake user repository -- no network
call to Supabase, no database. JWT internals (signature, claims, JWKS) are
already covered by ``test_supabase_jwt.py``; this file only exercises the
dependency chain and endpoint contract.
"""

import datetime
import uuid

import pytest
from httpx import AsyncClient

from app.api.deps import get_supabase_jwt_verifier, get_user_repository
from app.core.exceptions import AuthenticationError
from app.domain.entities.user import User
from app.domain.repositories.user import IUserRepository
from app.main import app


class FakeUserRepository(IUserRepository):
    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, User] = {}

    def seed(self, user: User) -> None:
        self._rows[user.id] = user

    def remove(self, user_id: uuid.UUID) -> None:
        self._rows.pop(user_id, None)

    async def get_by_authenticated_id(self, user_id: uuid.UUID) -> User | None:
        return self._rows.get(user_id)


    async def create(self, entity: User) -> User:
        raise NotImplementedError

    async def update(self, entity: User) -> User:
        raise NotImplementedError

    async def delete(self, entity: User) -> None:
        raise NotImplementedError


class FakeVerifier:
    """Stands in for ``SupabaseJWTVerifier``: maps a fixed token string to
    a fixed identity, or raises ``AuthenticationError`` for anything else.
    """

    def __init__(self) -> None:
        self.valid_tokens: dict[str, uuid.UUID] = {}

    def register(self, token: str, identity: uuid.UUID) -> None:
        self.valid_tokens[token] = identity

    def verify(self, token: str) -> uuid.UUID:
        if token not in self.valid_tokens:
            raise AuthenticationError("Invalid authentication credentials")
        return self.valid_tokens[token]


@pytest.fixture
def fake_repository() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def fake_verifier() -> FakeVerifier:
    return FakeVerifier()


@pytest.fixture(autouse=True)
def _override_dependencies(
    fake_repository: FakeUserRepository, fake_verifier: FakeVerifier
):
    app.dependency_overrides[get_supabase_jwt_verifier] = lambda: fake_verifier
    app.dependency_overrides[get_user_repository] = lambda: fake_repository
    yield
    app.dependency_overrides.pop(get_supabase_jwt_verifier, None)
    app.dependency_overrides.pop(get_user_repository, None)


async def test_missing_authorization_header_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_non_bearer_scheme_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me", headers={"Authorization": "Basic abc123"})
    assert response.status_code == 401


async def test_empty_bearer_credentials_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer "})
    assert response.status_code == 401


async def test_malformed_token_returns_401(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-registered-token"}
    )
    assert response.status_code == 401


async def test_expired_or_otherwise_rejected_token_returns_401(client: AsyncClient) -> None:
    # From the dependency's perspective, any verification failure (expired,
    # bad signature, wrong audience, ...) is indistinguishable -- already
    # covered exhaustively in test_supabase_jwt.py. Here it's simply an
    # unregistered token, exercising the same generic-401 path.
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer expired-token"}
    )
    assert response.status_code == 401


async def test_valid_identity_with_profile_returns_200(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    user_id = uuid.uuid4()
    organization_id = uuid.uuid4()
    fake_verifier.register("valid-token", user_id)
    fake_repository.seed(
        User(
            id=user_id,
            organization_id=organization_id,
            full_name="Test User",
            email="test@example.com",
            role="admin",
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
    )

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer valid-token"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user_id)
    assert body["organization_id"] == str(organization_id)
    assert body["full_name"] == "Test User"
    assert body["email"] == "test@example.com"
    assert body["role"] == "admin"
    assert set(body.keys()) == {"id", "organization_id", "full_name", "email", "role"}


async def test_valid_identity_without_profile_returns_403(
    client: AsyncClient, fake_verifier: FakeVerifier
) -> None:
    user_id = uuid.uuid4()
    fake_verifier.register("orphan-token", user_id)

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer orphan-token"}
    )

    assert response.status_code == 403


async def test_deleted_profile_after_token_issuance_returns_403(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    user_id = uuid.uuid4()
    fake_verifier.register("token-for-deleted-user", user_id)
    fake_repository.seed(
        User(
            id=user_id,
            organization_id=None,
            full_name="Ghost",
            email="ghost@example.com",
            role=None,
            created_at=None,
        )
    )
    fake_repository.remove(user_id)

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer token-for-deleted-user"}
    )

    assert response.status_code == 403


async def test_openapi_includes_auth_me_path(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/auth/me" in paths
    assert "get" in paths["/api/v1/auth/me"]
