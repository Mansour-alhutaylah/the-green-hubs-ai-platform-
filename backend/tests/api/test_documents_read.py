"""API-level tests for the Document list/detail read endpoints.

Uses FastAPI's ``dependency_overrides`` to substitute a test-controlled
Supabase JWT verifier, an in-memory fake user repository (reusing
``test_auth.py``'s fakes, exactly like ``test_documents.py``), and a
stub ``DocumentReadService`` -- no network call to Supabase, no
database. Tenant-scoping business rules (null organization -> 403,
foreign engagement/document -> 404) already have exhaustive coverage in
``test_document_read_service.py``; this file exercises the router's own
concerns: request parsing, query-parameter validation, delegation, and
the response contract.
"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.api.deps import get_document_read_service, get_supabase_jwt_verifier, get_user_repository
from app.core.exceptions import AuthorizationError, NotFoundError
from app.domain.entities.document_read_model import (
    AnalysisSummary,
    DocumentReadModel,
    EmbeddingSummary,
)
from app.domain.entities.user import User
from app.main import app

from tests.api.test_auth import FakeUserRepository, FakeVerifier

_EMPTY_EMBEDDING_SUMMARY = EmbeddingSummary(
    total_chunks=0, processing=0, completed=0, failed=0, is_complete=False
)


def _document(**overrides: object) -> DocumentReadModel:
    now = datetime.now(timezone.utc)
    defaults: dict = {
        "id": uuid.uuid4(),
        "engagement_id": uuid.uuid4(),
        "filename": "report.pdf",
        "processing_status": "PROCESSED",
        "created_at": now,
        "updated_at": now,
        "has_extracted_text": True,
        "chunk_count": 3,
        "embedding_summary": _EMPTY_EMBEDDING_SUMMARY,
        "latest_analysis_summary": None,
    }
    defaults.update(overrides)
    return DocumentReadModel(**defaults)


class StubDocumentReadService:
    def __init__(self) -> None:
        self.list_calls: list[dict] = []
        self.get_calls: list[uuid.UUID] = []
        self.list_result: tuple[list[DocumentReadModel], int] = ([], 0)
        self.get_result: DocumentReadModel | None = None
        self.error: Exception | None = None

    async def list(
        self,
        current_user: User,
        *,
        engagement_id: uuid.UUID | None,
        processing_status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[DocumentReadModel], int]:
        self.list_calls.append(
            {
                "engagement_id": engagement_id,
                "processing_status": processing_status,
                "limit": limit,
                "offset": offset,
            }
        )
        if self.error is not None:
            raise self.error
        return self.list_result

    async def get(self, document_id: uuid.UUID, current_user: User) -> DocumentReadModel:
        self.get_calls.append(document_id)
        if self.error is not None:
            raise self.error
        if self.get_result is None:
            raise NotFoundError(f"Document {document_id} not found")
        return self.get_result


@pytest.fixture
def fake_repository() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def fake_verifier() -> FakeVerifier:
    return FakeVerifier()


@pytest.fixture
def stub_service() -> StubDocumentReadService:
    return StubDocumentReadService()


@pytest.fixture(autouse=True)
def _override_dependencies(
    fake_repository: FakeUserRepository,
    fake_verifier: FakeVerifier,
    stub_service: StubDocumentReadService,
):
    app.dependency_overrides[get_supabase_jwt_verifier] = lambda: fake_verifier
    app.dependency_overrides[get_user_repository] = lambda: fake_repository
    app.dependency_overrides[get_document_read_service] = lambda: stub_service
    yield
    app.dependency_overrides.pop(get_supabase_jwt_verifier, None)
    app.dependency_overrides.pop(get_user_repository, None)
    app.dependency_overrides.pop(get_document_read_service, None)


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


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


async def test_list_documents_missing_authentication_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/documents")
    assert response.status_code == 401


async def test_get_document_missing_authentication_returns_401(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/documents/{uuid.uuid4()}")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Authorization (null organization)
# ---------------------------------------------------------------------------


async def test_list_documents_with_no_organization_returns_403(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubDocumentReadService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = AuthorizationError("User has no organization")

    response = await client.get("/api/v1/documents", headers=headers)

    assert response.status_code == 403


async def test_get_document_with_no_organization_returns_403(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubDocumentReadService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = AuthorizationError("User has no organization")

    response = await client.get(f"/api/v1/documents/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# List contract
# ---------------------------------------------------------------------------


async def test_list_documents_response_contract(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubDocumentReadService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    document = _document()
    stub_service.list_result = ([document], 1)

    response = await client.get("/api/v1/documents", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "limit", "offset"}
    assert body["total"] == 1
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert set(item.keys()) == {
        "id",
        "engagement_id",
        "filename",
        "processing_status",
        "created_at",
        "updated_at",
        "has_extracted_text",
        "chunk_count",
        "embedding_summary",
        "latest_analysis_summary",
    }
    assert item["id"] == str(document.id)
    assert "storage_path" not in item


async def test_list_documents_defaults_limit_and_offset(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubDocumentReadService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)

    response = await client.get("/api/v1/documents", headers=headers)

    assert response.status_code == 200
    assert stub_service.list_calls[-1]["limit"] == 20
    assert stub_service.list_calls[-1]["offset"] == 0


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
async def test_list_documents_invalid_pagination_returns_422(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    params: dict,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)

    response = await client.get("/api/v1/documents", headers=headers, params=params)

    assert response.status_code == 422


async def test_list_documents_invalid_processing_status_returns_422(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)

    response = await client.get(
        "/api/v1/documents", headers=headers, params={"processing_status": "NOT_A_REAL_STATUS"}
    )

    assert response.status_code == 422


async def test_list_documents_forwards_valid_filters(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubDocumentReadService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    engagement_id = uuid.uuid4()

    response = await client.get(
        "/api/v1/documents",
        headers=headers,
        params={
            "engagement_id": str(engagement_id),
            "processing_status": "FAILED",
            "limit": 5,
            "offset": 10,
        },
    )

    assert response.status_code == 200
    call = stub_service.list_calls[-1]
    assert call["engagement_id"] == engagement_id
    assert call["processing_status"] == "FAILED"
    assert call["limit"] == 5
    assert call["offset"] == 10


async def test_list_documents_foreign_engagement_returns_404(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubDocumentReadService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = NotFoundError("Engagement not found")

    response = await client.get(
        "/api/v1/documents", headers=headers, params={"engagement_id": str(uuid.uuid4())}
    )

    assert response.status_code == 404


async def test_list_documents_client_supplied_organization_id_is_ignored(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubDocumentReadService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)

    response = await client.get(
        "/api/v1/documents", headers=headers, params={"organization_id": str(uuid.uuid4())}
    )

    assert response.status_code == 200
    # The router has no organization_id parameter at all -- it is silently
    # ignored by FastAPI's query parsing, never reaching the service call.
    assert "organization_id" not in stub_service.list_calls[-1]


# ---------------------------------------------------------------------------
# Detail contract
# ---------------------------------------------------------------------------


async def test_get_document_response_contract(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubDocumentReadService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    document = _document(
        latest_analysis_summary=AnalysisSummary(
            id=uuid.uuid4(),
            status="COMPLETED",
            analysis_type="sustainability_summary",
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            overall_confidence=0.9,
        )
    )
    stub_service.get_result = document

    response = await client.get(f"/api/v1/documents/{document.id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "id",
        "engagement_id",
        "filename",
        "processing_status",
        "created_at",
        "updated_at",
        "has_extracted_text",
        "chunk_count",
        "embedding_summary",
        "latest_analysis_summary",
    }
    assert body["id"] == str(document.id)
    assert body["latest_analysis_summary"]["overall_confidence"] == 0.9
    assert "storage_path" not in body
    assert "structured_output" not in body["latest_analysis_summary"]
    assert "error_message" not in body["latest_analysis_summary"]


async def test_get_document_with_no_analysis_returns_null_summary(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubDocumentReadService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    document = _document(latest_analysis_summary=None)
    stub_service.get_result = document

    response = await client.get(f"/api/v1/documents/{document.id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["latest_analysis_summary"] is None


async def test_get_document_foreign_document_returns_404(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)

    response = await client.get(f"/api/v1/documents/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404


async def test_get_document_malformed_id_returns_422(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)

    response = await client.get("/api/v1/documents/not-a-uuid", headers=headers)

    assert response.status_code == 422


async def test_openapi_includes_document_list_and_detail_paths(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "get" in paths["/api/v1/documents"]
    assert "get" in paths["/api/v1/documents/{document_id}"]
