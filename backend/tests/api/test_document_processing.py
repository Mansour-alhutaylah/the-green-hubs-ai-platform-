"""API-level tests for the Document processing endpoint
(``POST /api/v1/documents/{document_id}/process``).

Uses FastAPI's ``dependency_overrides`` to substitute a test-controlled
Supabase JWT verifier, an in-memory fake user repository (reusing
``test_auth.py``'s fakes), and a stub ``DocumentProcessingService`` -- no
network call to Supabase, no database. Business-validation rules are
already exhaustively covered in ``test_document_processing_service.py``;
this file exercises the router's own concerns: authentication wiring,
delegation, status-code mapping via the registered exception handlers, and
the response contract (safe fields only -- never extracted text, chunks,
or storage_path).
"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.api.deps import (
    get_document_processing_service,
    get_supabase_jwt_verifier,
    get_user_repository,
)
from app.core.exceptions import (
    AuthorizationError,
    InvalidStateTransitionError,
    NotFoundError,
    PersistenceError,
    ValidationError,
)
from app.domain.entities.document import Document
from app.domain.entities.user import User
from app.main import app

from tests.api.test_auth import FakeUserRepository, FakeVerifier


class StubDocumentProcessingService:
    def __init__(self) -> None:
        self.calls: list[uuid.UUID] = []
        self.error: Exception | None = None
        self.result: Document | None = None

    async def process(self, document_id: uuid.UUID, current_user: User) -> Document:
        self.calls.append(document_id)
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        now = datetime.now(timezone.utc)
        return Document(
            id=document_id,
            filename="report.pdf",
            storage_path="organizations/x/engagements/y/documents/z.pdf",
            processing_status="PROCESSED",
            engagement_id=uuid.uuid4(),
            created_at=now,
            updated_at=now,
        )


@pytest.fixture
def fake_repository() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def fake_verifier() -> FakeVerifier:
    return FakeVerifier()


@pytest.fixture
def stub_service() -> StubDocumentProcessingService:
    return StubDocumentProcessingService()


@pytest.fixture(autouse=True)
def _override_dependencies(
    fake_repository: FakeUserRepository,
    fake_verifier: FakeVerifier,
    stub_service: StubDocumentProcessingService,
):
    app.dependency_overrides[get_supabase_jwt_verifier] = lambda: fake_verifier
    app.dependency_overrides[get_user_repository] = lambda: fake_repository
    app.dependency_overrides[get_document_processing_service] = lambda: stub_service
    yield
    app.dependency_overrides.pop(get_supabase_jwt_verifier, None)
    app.dependency_overrides.pop(get_user_repository, None)
    app.dependency_overrides.pop(get_document_processing_service, None)


def _authenticated_headers(fake_verifier: FakeVerifier, fake_repository: FakeUserRepository) -> dict:
    user_id = uuid.uuid4()
    fake_verifier.register("valid-token", user_id)
    fake_repository.seed(
        User(
            id=user_id,
            organization_id=uuid.uuid4(),
            full_name="Test User",
            email="test@example.com",
            role="admin",
            created_at=datetime.now(timezone.utc),
        )
    )
    return {"Authorization": "Bearer valid-token"}


async def test_missing_authentication_returns_401(client: AsyncClient) -> None:
    response = await client.post(f"/api/v1/documents/{uuid.uuid4()}/process")
    assert response.status_code == 401


async def test_invalid_token_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/v1/documents/{uuid.uuid4()}/process",
        headers={"Authorization": "Bearer not-a-registered-token"},
    )
    assert response.status_code == 401


async def test_malformed_document_id_returns_422(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    response = await client.post("/api/v1/documents/not-a-uuid/process", headers=headers)
    assert response.status_code == 422


async def test_delegates_to_service_with_document_id_and_current_user(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubDocumentProcessingService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    document_id = uuid.uuid4()

    response = await client.post(f"/api/v1/documents/{document_id}/process", headers=headers)

    assert response.status_code == 200
    assert stub_service.calls == [document_id]


async def test_successful_processing_returns_safe_response_fields(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)

    response = await client.post(f"/api/v1/documents/{uuid.uuid4()}/process", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "id",
        "engagement_id",
        "filename",
        "processing_status",
        "created_at",
        "updated_at",
    }
    assert body["processing_status"] == "PROCESSED"
    # Never leaked: internal storage details or extracted content/chunks.
    assert "storage_path" not in body
    assert "extracted_text" not in body
    assert "extracted_content" not in body
    assert "chunks" not in body


async def test_missing_document_returns_404(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubDocumentProcessingService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = NotFoundError("Document not found")

    response = await client.post(f"/api/v1/documents/{uuid.uuid4()}/process", headers=headers)

    assert response.status_code == 404


async def test_authorization_failure_returns_403(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubDocumentProcessingService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = AuthorizationError("User is not authorized for this engagement")

    response = await client.post(f"/api/v1/documents/{uuid.uuid4()}/process", headers=headers)

    assert response.status_code == 403


@pytest.mark.parametrize(
    "message",
    [
        "Document is already being processed.",
        "Document has already been processed.",
        "Failed documents cannot be reprocessed in this sprint.",
    ],
)
async def test_invalid_state_transition_returns_409_with_exact_message(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubDocumentProcessingService,
    message: str,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = InvalidStateTransitionError(message)

    response = await client.post(f"/api/v1/documents/{uuid.uuid4()}/process", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == message


async def test_validation_error_returns_422(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubDocumentProcessingService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = ValidationError("Extracted text is empty")

    response = await client.post(f"/api/v1/documents/{uuid.uuid4()}/process", headers=headers)

    assert response.status_code == 422


async def test_persistence_error_returns_500_without_leaking_internal_detail(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubDocumentProcessingService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = PersistenceError("Unable to retrieve the stored document")

    response = await client.post(f"/api/v1/documents/{uuid.uuid4()}/process", headers=headers)

    assert response.status_code == 500
    assert response.json()["detail"] == "Unable to retrieve the stored document"


async def test_openapi_includes_process_path(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/documents/{document_id}/process" in paths
    assert "post" in paths["/api/v1/documents/{document_id}/process"]
