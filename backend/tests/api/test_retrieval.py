"""API-level tests for the vector retrieval endpoint
(``POST /api/v1/retrieval/search``).

Uses FastAPI's ``dependency_overrides`` to substitute a test-controlled
Supabase JWT verifier, an in-memory fake user repository (reusing
``test_auth.py``'s fakes), and a stub ``VectorRetrievalService`` -- no
network call to Supabase, no database, no live OpenAI call.
"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.api.deps import get_supabase_jwt_verifier, get_user_repository, get_vector_retrieval_service
from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.domain.entities.user import User
from app.domain.entities.vector_search_result import VectorSearchResult
from app.main import app

from tests.api.test_auth import FakeUserRepository, FakeVerifier


class StubVectorRetrievalService:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.results: list[VectorSearchResult] = []

    async def search(self, current_user: User, *, query: str, top_k: int, engagement_id=None, document_id=None):
        self.calls.append(
            {
                "current_user": current_user, "query": query, "top_k": top_k,
                "engagement_id": engagement_id, "document_id": document_id,
            }
        )
        if self.error is not None:
            raise self.error
        return self.results


@pytest.fixture
def fake_repository() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def fake_verifier() -> FakeVerifier:
    return FakeVerifier()


@pytest.fixture
def stub_service() -> StubVectorRetrievalService:
    return StubVectorRetrievalService()


@pytest.fixture(autouse=True)
def _override_dependencies(
    fake_repository: FakeUserRepository,
    fake_verifier: FakeVerifier,
    stub_service: StubVectorRetrievalService,
):
    app.dependency_overrides[get_supabase_jwt_verifier] = lambda: fake_verifier
    app.dependency_overrides[get_user_repository] = lambda: fake_repository
    app.dependency_overrides[get_vector_retrieval_service] = lambda: stub_service
    yield
    app.dependency_overrides.pop(get_supabase_jwt_verifier, None)
    app.dependency_overrides.pop(get_user_repository, None)
    app.dependency_overrides.pop(get_vector_retrieval_service, None)


def _authenticated_headers(fake_verifier: FakeVerifier, fake_repository: FakeUserRepository) -> dict:
    user_id = uuid.uuid4()
    fake_verifier.register("valid-token", user_id)
    fake_repository.seed(
        User(
            id=user_id, organization_id=uuid.uuid4(), full_name="Test User",
            email="test@example.com", role=None, created_at=datetime.now(timezone.utc),
        )
    )
    return {"Authorization": "Bearer valid-token"}


async def test_missing_authentication_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/retrieval/search", json={"query": "emissions", "top_k": 5}
    )
    assert response.status_code == 401


async def test_invalid_token_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/retrieval/search",
        headers={"Authorization": "Bearer not-a-registered-token"},
        json={"query": "emissions", "top_k": 5},
    )
    assert response.status_code == 401


async def test_empty_query_returns_422(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    response = await client.post(
        "/api/v1/retrieval/search", headers=headers, json={"query": "   ", "top_k": 5}
    )
    assert response.status_code == 422


async def test_missing_top_k_returns_422(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    response = await client.post(
        "/api/v1/retrieval/search", headers=headers, json={"query": "emissions"}
    )
    assert response.status_code == 422


@pytest.mark.parametrize("top_k", [0, -1, 51])
async def test_out_of_range_top_k_returns_422(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    top_k: int,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    response = await client.post(
        "/api/v1/retrieval/search", headers=headers, json={"query": "emissions", "top_k": top_k}
    )
    assert response.status_code == 422


async def test_organization_id_field_is_rejected_or_ignored(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubVectorRetrievalService,
) -> None:
    """organization_id must never be an accepted request field -- Pydantic
    silently ignores unknown fields by default, so this proves it never
    reaches the service, not merely that it's absent from the schema."""
    headers = _authenticated_headers(fake_verifier, fake_repository)
    foreign_org_id = str(uuid.uuid4())

    response = await client.post(
        "/api/v1/retrieval/search",
        headers=headers,
        json={"query": "emissions", "top_k": 5, "organization_id": foreign_org_id},
    )

    assert response.status_code == 200
    call = stub_service.calls[0]
    assert "organization_id" not in call
    assert foreign_org_id not in str(call)


async def test_null_organization_returns_403(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubVectorRetrievalService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = AuthorizationError("User has no organization")

    response = await client.post(
        "/api/v1/retrieval/search", headers=headers, json={"query": "emissions", "top_k": 5}
    )

    assert response.status_code == 403


async def test_inaccessible_engagement_returns_404(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubVectorRetrievalService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = NotFoundError("Engagement not found")

    response = await client.post(
        "/api/v1/retrieval/search",
        headers=headers,
        json={"query": "emissions", "top_k": 5, "engagement_id": str(uuid.uuid4())},
    )

    assert response.status_code == 404


async def test_inconsistent_engagement_and_document_returns_422(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubVectorRetrievalService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = ValidationError("document does not belong to the specified engagement")

    response = await client.post(
        "/api/v1/retrieval/search",
        headers=headers,
        json={
            "query": "emissions", "top_k": 5,
            "engagement_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 422


async def test_successful_search_returns_safe_result_shape(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubVectorRetrievalService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    chunk_id, document_id, engagement_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    stub_service.results = [
        VectorSearchResult(
            chunk_id=chunk_id, document_id=document_id, engagement_id=engagement_id,
            chunk_index=2, content="Scope 1 emissions decreased by 12%.", char_start=100,
            char_end=136, similarity_score=0.87,
        )
    ]

    response = await client.post(
        "/api/v1/retrieval/search", headers=headers, json={"query": "emissions", "top_k": 5}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert set(item.keys()) == {
        "chunk_id", "document_id", "engagement_id", "chunk_index", "content",
        "similarity_score", "char_start", "char_end",
    }
    assert item["chunk_id"] == str(chunk_id)
    assert item["similarity_score"] == pytest.approx(0.87)
    # never leaked
    assert "embedding" not in item
    assert "vector" not in item
    assert "content_hash" not in item
    assert "provider" not in item
    assert "status" not in item
    assert "error_message" not in item


async def test_openapi_includes_retrieval_search_path(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/retrieval/search" in paths
    assert "post" in paths["/api/v1/retrieval/search"]
