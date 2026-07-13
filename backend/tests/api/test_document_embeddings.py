"""API-level tests for the embedding generation endpoint
(``POST /api/v1/documents/{document_id}/embeddings``).

Uses FastAPI's ``dependency_overrides`` to substitute a test-controlled
Supabase JWT verifier, an in-memory fake user repository (reusing
``test_auth.py``'s fakes), and a stub ``EmbeddingGenerationService`` --
no network call to Supabase, no database. Business logic (tenant checks,
state classification, idempotency) is already exhaustively covered in
``test_embedding_generation_service.py``; this file exercises the
router's own concerns: authentication wiring, delegation, status-code
mapping, and the safe summary response contract.
"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.api.deps import (
    get_embedding_generation_service,
    get_supabase_jwt_verifier,
    get_user_repository,
)
from app.core.exceptions import (
    AuthorizationError,
    InvalidStateTransitionError,
    NotFoundError,
)
from app.domain.entities.user import User
from app.main import app
from app.services.embedding_generation import EmbeddingGenerationSummary

from tests.api.test_auth import FakeUserRepository, FakeVerifier


class StubEmbeddingGenerationService:
    def __init__(self) -> None:
        self.calls: list[uuid.UUID] = []
        self.error: Exception | None = None
        self.summary: EmbeddingGenerationSummary | None = None

    async def generate_for_document(
        self, document_id: uuid.UUID, current_user: User
    ) -> EmbeddingGenerationSummary:
        self.calls.append(document_id)
        if self.error is not None:
            raise self.error
        if self.summary is not None:
            return self.summary
        return EmbeddingGenerationSummary(
            document_id=document_id, total_chunks=5, newly_completed=5, already_completed=0,
            failed=0, in_progress=0, conflicts=0,
        )


@pytest.fixture
def fake_repository() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def fake_verifier() -> FakeVerifier:
    return FakeVerifier()


@pytest.fixture
def stub_service() -> StubEmbeddingGenerationService:
    return StubEmbeddingGenerationService()


@pytest.fixture(autouse=True)
def _override_dependencies(
    fake_repository: FakeUserRepository,
    fake_verifier: FakeVerifier,
    stub_service: StubEmbeddingGenerationService,
):
    app.dependency_overrides[get_supabase_jwt_verifier] = lambda: fake_verifier
    app.dependency_overrides[get_user_repository] = lambda: fake_repository
    app.dependency_overrides[get_embedding_generation_service] = lambda: stub_service
    yield
    app.dependency_overrides.pop(get_supabase_jwt_verifier, None)
    app.dependency_overrides.pop(get_user_repository, None)
    app.dependency_overrides.pop(get_embedding_generation_service, None)


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
    response = await client.post(f"/api/v1/documents/{uuid.uuid4()}/embeddings")
    assert response.status_code == 401


async def test_invalid_token_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/v1/documents/{uuid.uuid4()}/embeddings",
        headers={"Authorization": "Bearer not-a-registered-token"},
    )
    assert response.status_code == 401


async def test_delegates_to_service_with_document_id(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubEmbeddingGenerationService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    document_id = uuid.uuid4()

    response = await client.post(f"/api/v1/documents/{document_id}/embeddings", headers=headers)

    assert response.status_code == 200
    assert stub_service.calls == [document_id]


async def test_successful_generation_returns_safe_summary(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)

    response = await client.post(f"/api/v1/documents/{uuid.uuid4()}/embeddings", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "document_id", "total_chunks", "newly_completed", "already_completed",
        "failed", "in_progress", "conflicts",
    }
    assert body["newly_completed"] == 5
    # never a raw vector or provider detail anywhere in the response
    assert "embedding" not in body
    assert "vector" not in body
    assert "error_message" not in body


async def test_missing_document_returns_404(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubEmbeddingGenerationService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = NotFoundError("Document not found")

    response = await client.post(f"/api/v1/documents/{uuid.uuid4()}/embeddings", headers=headers)

    assert response.status_code == 404


async def test_authorization_failure_returns_403(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubEmbeddingGenerationService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = AuthorizationError("User has no organization")

    response = await client.post(f"/api/v1/documents/{uuid.uuid4()}/embeddings", headers=headers)

    assert response.status_code == 403


async def test_unprocessed_document_returns_409(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubEmbeddingGenerationService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = InvalidStateTransitionError(
        "Document must be processed before embeddings can be generated."
    )

    response = await client.post(f"/api/v1/documents/{uuid.uuid4()}/embeddings", headers=headers)

    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "Document must be processed before embeddings can be generated."
    )


async def test_partial_failure_summary_still_returns_200(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubEmbeddingGenerationService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    document_id = uuid.uuid4()
    stub_service.summary = EmbeddingGenerationSummary(
        document_id=document_id, total_chunks=10, newly_completed=6, already_completed=2,
        failed=1, in_progress=0, conflicts=1,
    )

    response = await client.post(f"/api/v1/documents/{document_id}/embeddings", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["failed"] == 1
    assert body["conflicts"] == 1


async def test_openapi_includes_embeddings_path(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/documents/{document_id}/embeddings" in paths
    assert "post" in paths["/api/v1/documents/{document_id}/embeddings"]
