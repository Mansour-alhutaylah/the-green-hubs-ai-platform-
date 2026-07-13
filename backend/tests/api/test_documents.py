"""API-level tests for the Document upload endpoint.

Uses FastAPI's ``dependency_overrides`` to substitute a test-controlled
Supabase JWT verifier, an in-memory fake user repository (reusing
``test_auth.py``'s fakes), and a stub ``DocumentUploadService`` -- no
network call to Supabase, no database. Business-validation rules (PDF
signature, size limits, organization authorization, etc.) are already
exhaustively covered in ``test_document_upload_service.py``; this file
exercises the router's own concerns: request parsing, bounded/chunked
reading, delegation, and the response contract.
"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.api.deps import (
    get_app_settings,
    get_document_upload_service,
    get_supabase_jwt_verifier,
    get_user_repository,
)
from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.domain.entities.document import Document
from app.domain.entities.user import User
from app.main import app
from app.services.document_upload import DocumentUploadInput

from tests.api.test_auth import FakeUserRepository, FakeVerifier

PDF_BYTES = b"%PDF-1.4\n%Fake PDF content for tests\n%%EOF"


class StubDocumentUploadService:
    def __init__(self) -> None:
        self.calls: list[DocumentUploadInput] = []
        self.error: Exception | None = None

    async def upload(self, request: DocumentUploadInput, *, current_user: User) -> Document:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        now = datetime.now(timezone.utc)
        return Document(
            id=uuid.uuid4(),
            filename=request.original_filename,
            storage_path="organizations/x/engagements/y/documents/z.pdf",
            processing_status="PENDING",
            engagement_id=request.engagement_id,
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
def stub_service() -> StubDocumentUploadService:
    return StubDocumentUploadService()


@pytest.fixture(autouse=True)
def _override_dependencies(
    fake_repository: FakeUserRepository,
    fake_verifier: FakeVerifier,
    stub_service: StubDocumentUploadService,
):
    app.dependency_overrides[get_supabase_jwt_verifier] = lambda: fake_verifier
    app.dependency_overrides[get_user_repository] = lambda: fake_repository
    app.dependency_overrides[get_document_upload_service] = lambda: stub_service
    yield
    app.dependency_overrides.pop(get_supabase_jwt_verifier, None)
    app.dependency_overrides.pop(get_user_repository, None)
    app.dependency_overrides.pop(get_document_upload_service, None)


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
    response = await client.post(
        "/api/v1/documents",
        data={"engagement_id": str(uuid.uuid4())},
        files={"file": ("report.pdf", PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == 401


async def test_invalid_token_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/documents",
        headers={"Authorization": "Bearer not-a-registered-token"},
        data={"engagement_id": str(uuid.uuid4())},
        files={"file": ("report.pdf", PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == 401


async def test_missing_file_returns_422(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    response = await client.post(
        "/api/v1/documents", headers=headers, data={"engagement_id": str(uuid.uuid4())}
    )
    assert response.status_code == 422


async def test_malformed_engagement_id_returns_422(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    response = await client.post(
        "/api/v1/documents",
        headers=headers,
        data={"engagement_id": "not-a-uuid"},
        files={"file": ("report.pdf", PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == 422


async def test_non_pdf_content_rejected_via_service_validation_error(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubDocumentUploadService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = ValidationError("file content does not match the PDF format")

    response = await client.post(
        "/api/v1/documents",
        headers=headers,
        data={"engagement_id": str(uuid.uuid4())},
        files={"file": ("report.pdf", b"not actually a pdf", "application/pdf")},
    )

    assert response.status_code == 422
    assert len(stub_service.calls) == 1
    assert stub_service.calls[0].content == b"not actually a pdf"
    assert stub_service.calls[0].original_filename == "report.pdf"
    assert stub_service.calls[0].declared_content_type == "application/pdf"


async def test_misleading_extension_rejected_via_service_validation_error(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubDocumentUploadService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = ValidationError("file must have a .pdf extension")

    response = await client.post(
        "/api/v1/documents",
        headers=headers,
        data={"engagement_id": str(uuid.uuid4())},
        files={"file": ("report.txt", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 422


async def test_incorrect_declared_content_type_is_forwarded_to_service(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubDocumentUploadService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = ValidationError("file must be declared as application/pdf")

    response = await client.post(
        "/api/v1/documents",
        headers=headers,
        data={"engagement_id": str(uuid.uuid4())},
        files={"file": ("report.pdf", PDF_BYTES, "text/plain")},
    )

    assert response.status_code == 422
    assert stub_service.calls[0].declared_content_type == "text/plain"


async def test_file_exceeding_configured_limit_returns_422(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)

    def tiny_limit_settings() -> Settings:
        return Settings(max_upload_size_bytes=10)

    app.dependency_overrides[get_app_settings] = tiny_limit_settings
    try:
        response = await client.post(
            "/api/v1/documents",
            headers=headers,
            data={"engagement_id": str(uuid.uuid4())},
            files={"file": ("report.pdf", PDF_BYTES, "application/pdf")},  # > 10 bytes
        )
    finally:
        app.dependency_overrides.pop(get_app_settings, None)

    assert response.status_code == 422


async def test_successful_upload_returns_safe_response_fields(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)

    response = await client.post(
        "/api/v1/documents",
        headers=headers,
        data={"engagement_id": str(uuid.uuid4())},
        files={"file": ("report.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body.keys()) == {
        "id",
        "engagement_id",
        "filename",
        "processing_status",
        "created_at",
        "updated_at",
    }
    assert "storage_path" not in body
    assert body["filename"] == "report.pdf"
    assert body["processing_status"] == "PENDING"


async def test_openapi_includes_documents_path(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/documents" in paths
    assert "post" in paths["/api/v1/documents"]


# ---------------------------------------------------------------------------
# Bounded/chunked reading -- direct tests of the router's read helper
# ---------------------------------------------------------------------------


class _FakeUploadFile:
    def __init__(self, content: bytes) -> None:
        self._remaining = content
        self.read_calls: list[int] = []
        self.closed = False

    async def read(self, size: int) -> bytes:
        self.read_calls.append(size)
        chunk, self._remaining = self._remaining[:size], self._remaining[size:]
        return chunk

    async def close(self) -> None:
        self.closed = True


async def test_read_bounded_reads_in_multiple_chunks_not_all_at_once() -> None:
    from app.api.v1.documents import _CHUNK_SIZE_BYTES, _read_bounded

    content = b"x" * (_CHUNK_SIZE_BYTES * 3)
    fake_file = _FakeUploadFile(content)

    result = await _read_bounded(fake_file, max_size_bytes=len(content))  # type: ignore[arg-type]

    assert result == content
    assert len(fake_file.read_calls) > 1
    assert all(size == _CHUNK_SIZE_BYTES for size in fake_file.read_calls[:-1])
    assert fake_file.closed is True


async def test_read_bounded_stops_and_raises_when_exceeding_limit() -> None:
    from app.api.v1.documents import _CHUNK_SIZE_BYTES, _read_bounded

    content = b"x" * (_CHUNK_SIZE_BYTES * 3)  # far larger than the limit below
    fake_file = _FakeUploadFile(content)
    max_size = _CHUNK_SIZE_BYTES // 2  # smaller than a single chunk

    with pytest.raises(ValidationError):
        await _read_bounded(fake_file, max_size_bytes=max_size)  # type: ignore[arg-type]

    assert fake_file.closed is True
    assert len(fake_file.read_calls) == 1  # stopped immediately, after just the first chunk


async def test_read_bounded_closes_file_even_for_empty_stream() -> None:
    from app.api.v1.documents import _read_bounded

    fake_file = _FakeUploadFile(b"")

    result = await _read_bounded(fake_file, max_size_bytes=100)  # type: ignore[arg-type]

    assert result == b""
    assert fake_file.closed is True
