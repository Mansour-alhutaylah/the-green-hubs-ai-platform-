"""API-level tests for the RAG analysis endpoints
(``POST /api/v1/analysis/documents/{document_id}/analyze``,
``POST /api/v1/analysis/engagements/{engagement_id}/analyze``,
``GET /api/v1/analysis/runs/{analysis_run_id}``).

Uses FastAPI's ``dependency_overrides`` to substitute a test-controlled
Supabase JWT verifier, an in-memory fake user repository (reusing
``test_auth.py``'s fakes), and a stub ``RagAnalysisService`` -- no
network call to Supabase, no database, no live OpenAI call.
"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.api.deps import get_rag_analysis_service, get_supabase_jwt_verifier, get_user_repository
from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.domain.entities.user import User
from app.main import app
from app.services.analysis.rag_analysis import AnalysisResultView, CitationView

from tests.api.test_auth import FakeUserRepository, FakeVerifier


class StubRagAnalysisService:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.view: AnalysisResultView | None = None

    def _default_view(
        self, *, engagement_id: uuid.UUID, document_id: uuid.UUID | None
    ) -> AnalysisResultView:
        now = datetime.now(timezone.utc)
        return AnalysisResultView(
            analysis_run_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            engagement_id=engagement_id,
            document_id=document_id,
            status="COMPLETED",
            analysis_type="sustainability_summary",
            structured_output={
                "analysis_type": "sustainability_summary",
                "evidence_status": "sufficient",
                "insufficient_evidence_reason": None,
                "executive_summary": "ok",
                "reporting_period": None,
                "detected_topics": [],
                "reported_metrics": [],
                "key_findings": [],
                "recommendations": [],
                "overall_confidence": 0.8,
            },
            insufficient_evidence_reason=None,
            error_message=None,
            citations=[],
            created_at=now,
            updated_at=now,
            completed_at=now,
        )

    async def analyze_document(
        self, current_user: User, document_id: uuid.UUID, *, analysis_type: str, query_text: str
    ) -> AnalysisResultView:
        self.calls.append(
            {
                "current_user": current_user, "document_id": document_id,
                "analysis_type": analysis_type, "query_text": query_text,
            }
        )
        if self.error is not None:
            raise self.error
        return self.view or self._default_view(engagement_id=uuid.uuid4(), document_id=document_id)

    async def analyze_engagement(
        self, current_user: User, engagement_id: uuid.UUID, *, analysis_type: str, query_text: str
    ) -> AnalysisResultView:
        self.calls.append(
            {
                "current_user": current_user, "engagement_id": engagement_id,
                "analysis_type": analysis_type, "query_text": query_text,
            }
        )
        if self.error is not None:
            raise self.error
        return self.view or self._default_view(engagement_id=engagement_id, document_id=None)

    async def get_run(
        self, current_user: User, analysis_run_id: uuid.UUID
    ) -> AnalysisResultView:
        self.calls.append({"current_user": current_user, "analysis_run_id": analysis_run_id})
        if self.error is not None:
            raise self.error
        return self.view or self._default_view(engagement_id=uuid.uuid4(), document_id=None)


@pytest.fixture
def fake_repository() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def fake_verifier() -> FakeVerifier:
    return FakeVerifier()


@pytest.fixture
def stub_service() -> StubRagAnalysisService:
    return StubRagAnalysisService()


@pytest.fixture(autouse=True)
def _override_dependencies(
    fake_repository: FakeUserRepository,
    fake_verifier: FakeVerifier,
    stub_service: StubRagAnalysisService,
):
    app.dependency_overrides[get_supabase_jwt_verifier] = lambda: fake_verifier
    app.dependency_overrides[get_user_repository] = lambda: fake_repository
    app.dependency_overrides[get_rag_analysis_service] = lambda: stub_service
    yield
    app.dependency_overrides.pop(get_supabase_jwt_verifier, None)
    app.dependency_overrides.pop(get_user_repository, None)
    app.dependency_overrides.pop(get_rag_analysis_service, None)


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


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


async def test_analyze_document_missing_authentication_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/v1/analysis/documents/{uuid.uuid4()}/analyze",
        json={"analysis_type": "sustainability_summary", "query_text": "q"},
    )
    assert response.status_code == 401


async def test_analyze_engagement_missing_authentication_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/v1/analysis/engagements/{uuid.uuid4()}/analyze",
        json={"analysis_type": "sustainability_summary", "query_text": "q"},
    )
    assert response.status_code == 401


async def test_get_run_missing_authentication_returns_401(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/analysis/runs/{uuid.uuid4()}")
    assert response.status_code == 401


async def test_invalid_token_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/v1/analysis/documents/{uuid.uuid4()}/analyze",
        headers={"Authorization": "Bearer not-a-registered-token"},
        json={"analysis_type": "sustainability_summary", "query_text": "q"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------


async def test_blank_query_text_returns_422(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    response = await client.post(
        f"/api/v1/analysis/documents/{uuid.uuid4()}/analyze",
        headers=headers,
        json={"analysis_type": "sustainability_summary", "query_text": "   "},
    )
    assert response.status_code == 422


async def test_missing_analysis_type_returns_422(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    response = await client.post(
        f"/api/v1/analysis/documents/{uuid.uuid4()}/analyze",
        headers=headers,
        json={"query_text": "q"},
    )
    assert response.status_code == 422


async def test_service_validation_error_returns_422(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository,
    stub_service: StubRagAnalysisService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = ValidationError("analysis_type must be one of [...]")

    response = await client.post(
        f"/api/v1/analysis/documents/{uuid.uuid4()}/analyze",
        headers=headers,
        json={"analysis_type": "not_a_real_type", "query_text": "q"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tenant safety
# ---------------------------------------------------------------------------


async def test_null_organization_returns_403(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository,
    stub_service: StubRagAnalysisService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = AuthorizationError("User has no organization")

    response = await client.post(
        f"/api/v1/analysis/documents/{uuid.uuid4()}/analyze",
        headers=headers,
        json={"analysis_type": "sustainability_summary", "query_text": "q"},
    )
    assert response.status_code == 403


async def test_inaccessible_document_returns_404(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository,
    stub_service: StubRagAnalysisService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = NotFoundError("Document not found")

    response = await client.post(
        f"/api/v1/analysis/documents/{uuid.uuid4()}/analyze",
        headers=headers,
        json={"analysis_type": "sustainability_summary", "query_text": "q"},
    )
    assert response.status_code == 404


async def test_inaccessible_engagement_returns_404(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository,
    stub_service: StubRagAnalysisService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = NotFoundError("Engagement not found")

    response = await client.post(
        f"/api/v1/analysis/engagements/{uuid.uuid4()}/analyze",
        headers=headers,
        json={"analysis_type": "sustainability_summary", "query_text": "q"},
    )
    assert response.status_code == 404


async def test_foreign_analysis_run_returns_404(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository,
    stub_service: StubRagAnalysisService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    stub_service.error = NotFoundError("Analysis run not found")

    response = await client.get(f"/api/v1/analysis/runs/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


async def test_organization_id_field_is_ignored(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository,
    stub_service: StubRagAnalysisService,
) -> None:
    """organization_id must never be an accepted request field -- Pydantic
    silently ignores unknown fields by default, so this proves it never
    reaches the service, not merely that it's absent from the schema."""
    headers = _authenticated_headers(fake_verifier, fake_repository)
    foreign_org_id = str(uuid.uuid4())

    response = await client.post(
        f"/api/v1/analysis/documents/{uuid.uuid4()}/analyze",
        headers=headers,
        json={
            "analysis_type": "sustainability_summary", "query_text": "q",
            "organization_id": foreign_org_id,
        },
    )

    assert response.status_code == 200
    call = stub_service.calls[0]
    assert "organization_id" not in call
    assert foreign_org_id not in str(call)


# ---------------------------------------------------------------------------
# Idempotent duplicate request
# ---------------------------------------------------------------------------


async def test_identical_duplicate_request_returns_same_run_id(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository,
    stub_service: StubRagAnalysisService,
) -> None:
    """The API layer itself is stateless per call -- idempotency is proven
    at the service/repository layer -- but this confirms the endpoint
    faithfully echoes back whatever run the service considers canonical
    for repeated identical calls (the stub simulates that by returning a
    fixed view)."""
    headers = _authenticated_headers(fake_verifier, fake_repository)
    engagement_id = uuid.uuid4()
    fixed_view = stub_service._default_view(engagement_id=engagement_id, document_id=None)
    stub_service.view = fixed_view

    first = await client.post(
        f"/api/v1/analysis/engagements/{engagement_id}/analyze",
        headers=headers,
        json={"analysis_type": "sustainability_summary", "query_text": "q"},
    )
    second = await client.post(
        f"/api/v1/analysis/engagements/{engagement_id}/analyze",
        headers=headers,
        json={"analysis_type": "sustainability_summary", "query_text": "q"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["analysis_run_id"] == second.json()["analysis_run_id"]


# ---------------------------------------------------------------------------
# Safe response contract
# ---------------------------------------------------------------------------


async def test_successful_analysis_returns_safe_response_shape(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository,
    stub_service: StubRagAnalysisService,
) -> None:
    headers = _authenticated_headers(fake_verifier, fake_repository)
    citation_id = uuid.uuid4()
    document_id = uuid.uuid4()
    engagement_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    stub_service.view = AnalysisResultView(
        analysis_run_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        engagement_id=engagement_id,
        document_id=document_id,
        status="COMPLETED",
        analysis_type="sustainability_summary",
        structured_output={
            "analysis_type": "sustainability_summary",
            "evidence_status": "sufficient",
            "insufficient_evidence_reason": None,
            "executive_summary": "Scope 1 emissions decreased.",
            "reporting_period": "FY2025",
            "detected_topics": ["emissions"],
            "reported_metrics": [
                {
                    "name": "Scope 1", "status": "stated", "value": "1000", "unit": "tCO2e",
                    "period": "FY2025", "citation_ids": [str(citation_id)],
                }
            ],
            "key_findings": [
                {"statement": "Emissions decreased.", "citation_ids": [str(citation_id)]}
            ],
            "recommendations": [],
            "overall_confidence": 0.8,
        },
        insufficient_evidence_reason=None,
        error_message=None,
        citations=[
            CitationView(
                id=citation_id, document_id=document_id, chunk_index=0, char_start=0,
                char_end=28, quoted_snippet="Scope 1 emissions decreased.", citation_order=1,
                relevance_score=0.93,
            )
        ],
        created_at=now, updated_at=now, completed_at=now,
    )

    response = await client.post(
        f"/api/v1/analysis/documents/{document_id}/analyze",
        headers=headers,
        json={"analysis_type": "sustainability_summary", "query_text": "q"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["citations"][0]["id"] == str(citation_id)
    finding = body["structured_output"]["key_findings"][0]
    assert finding["citation_ids"] == [str(citation_id)]
    # never leaked to the client
    assert "organization_id" not in body
    assert "source_keys" not in str(body)
    assert "SOURCE_" not in str(body)
    assert "embedding" not in str(body)
    assert "vector" not in str(body)


async def test_openapi_includes_analysis_paths(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/analysis/documents/{document_id}/analyze" in paths
    assert "/api/v1/analysis/engagements/{engagement_id}/analyze" in paths
    assert "/api/v1/analysis/runs/{analysis_run_id}" in paths
