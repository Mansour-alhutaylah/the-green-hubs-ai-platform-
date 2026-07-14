"""Focused end-to-end integration tests for the RAG analysis endpoints,
exercised through the real ``app`` against the real database. Both the
embedding provider and the LLM gateway are swapped for deterministic
in-memory fakes via ``dependency_overrides`` -- no live OpenAI call,
matching this project's existing "never call live external AI/network
services in tests" discipline. Real pgvector storage, real
cosine-similarity retrieval, and real tenant-lineage-derived citation
persistence are exercised end-to-end.

Every row a test creates is tracked and cleaned up in dependency-safe
order: analysis_source_references, analysis_runs, document_chunk_embeddings,
document_chunks, documents, users, engagements, organizations, via an
independent session in teardown, regardless of test outcome.
"""

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, Sequence

import pytest
from httpx import AsyncClient

from app.api.deps import get_embedding_provider, get_llm_gateway, get_supabase_jwt_verifier
from app.core.config import get_settings
from app.domain.embedding_provider import EmbeddingProvider, EmbeddingResult
from app.domain.llm_gateway import LLMGateway, LLMProviderUnavailableError, LLMStructuredResult
from app.infrastructure.db.models.analysis_run import AnalysisRunModel
from app.infrastructure.db.models.analysis_source_reference import AnalysisSourceReferenceModel
from app.infrastructure.db.models.document import DocumentModel
from app.infrastructure.db.models.document_chunk import DocumentChunkModel
from app.infrastructure.db.models.document_chunk_embedding import DocumentChunkEmbeddingModel
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

DIMENSION = 1536
EMBEDDING_MODEL_VERSION = ""

VALID_STRUCTURED_OUTPUT = {
    "analysis_type": "sustainability_summary",
    "evidence_status": "sufficient",
    "insufficient_evidence_reason": None,
    "executive_summary": "Scope 1 emissions decreased year over year.",
    "reporting_period": "FY2025",
    "detected_topics": ["emissions"],
    "reported_metrics": [
        {
            "name": "Scope 1 emissions", "status": "stated", "value": "1000", "unit": "tCO2e",
            "period": "FY2025", "source_keys": ["SOURCE_1"],
        }
    ],
    "key_findings": [{"statement": "Emissions decreased.", "source_keys": ["SOURCE_1"]}],
    "recommendations": [{"statement": "Continue trend.", "source_keys": ["SOURCE_1"]}],
    "overall_confidence": 0.8,
}


def _deterministic_vector(text: str) -> list[float]:
    """A cheap, deterministic 1536-dim vector derived from the text's hash
    -- close for near-identical inputs, far apart otherwise -- standing
    in for a real embedding without any network dependency. Mirrors
    ``test_embedding_and_retrieval_integration.py``'s helper exactly."""
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
    return [((seed >> (i % 64)) % 1000) / 1000.0 for i in range(DIMENSION)]


class FakeEmbeddingProvider(EmbeddingProvider):
    async def embed_texts(self, texts: Sequence[str]) -> Sequence[EmbeddingResult]:
        return [
            EmbeddingResult(text=t, vector=_deterministic_vector(t), dimension=DIMENSION)
            for t in texts
        ]


class FakeLLMGateway(LLMGateway):
    """Returns queued responses in order; ignores the validator callback
    entirely (the real gateway's validator-retry behavior is already
    covered by ``test_openai_llm_gateway.py``'s unit tests -- these
    integration tests exercise what ``RagAnalysisService`` does with
    whatever the gateway ultimately returns)."""

    def __init__(self, responses: Sequence[dict | Exception]) -> None:
        self._responses = list(responses)
        self.call_count = 0

    async def complete_structured(
        self, *, system_prompt: str, user_prompt: str, validator=None
    ) -> LLMStructuredResult:
        self.call_count += 1
        if not self._responses:
            raise AssertionError("FakeLLMGateway ran out of queued responses")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMStructuredResult(
            raw_text=json.dumps(item), parsed=item, prompt_tokens=10, completion_tokens=20,
            total_tokens=30, model="gpt-4o-mini", finish_reason="stop",
        )


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


@pytest.fixture
def fake_llm_gateway() -> FakeLLMGateway:
    return FakeLLMGateway([])


@pytest.fixture(autouse=True)
def _override_dependencies(keypair, real_verifier: SupabaseJWTVerifier, fake_llm_gateway):
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
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    app.dependency_overrides[get_llm_gateway] = lambda: fake_llm_gateway
    yield
    app.dependency_overrides.pop(get_supabase_jwt_verifier, None)
    app.dependency_overrides.pop(get_embedding_provider, None)
    app.dependency_overrides.pop(get_llm_gateway, None)


@pytest.fixture
async def cleanup_ids() -> AsyncIterator[dict[str, list[uuid.UUID]]]:
    ids: dict[str, list[uuid.UUID]] = {
        "citations": [], "runs": [], "embeddings": [], "chunks": [], "documents": [],
        "users": [], "engagements": [], "organizations": [],
    }
    yield ids
    async with AsyncSessionLocal() as cleanup_session:
        for citation_id in ids["citations"]:
            model = await cleanup_session.get(AnalysisSourceReferenceModel, citation_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for run_id in ids["runs"]:
            model = await cleanup_session.get(AnalysisRunModel, run_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for embedding_id in ids["embeddings"]:
            model = await cleanup_session.get(DocumentChunkEmbeddingModel, embedding_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for chunk_id in ids["chunks"]:
            model = await cleanup_session.get(DocumentChunkModel, chunk_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for document_id in ids["documents"]:
            model = await cleanup_session.get(DocumentModel, document_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for user_id in ids["users"]:
            model = await cleanup_session.get(UserModel, user_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for engagement_id in ids["engagements"]:
            model = await cleanup_session.get(EngagementModel, engagement_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for organization_id in ids["organizations"]:
            model = await cleanup_session.get(OrganizationModel, organization_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()


async def _make_org_engagement_document_with_embedded_chunks(
    cleanup_ids: dict[str, list[uuid.UUID]], *, chunk_contents: list[str]
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Returns (organization_id, engagement_id, profile_id, document_id).
    Every chunk is given a real, COMPLETED DocumentChunkEmbeddingModel row
    with a deterministic vector, so RagAnalysisService's retrieval step
    finds real, tenant-scoped matches without any network call."""
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        organization = OrganizationModel(name="Analysis Integration Test Org")
        session.add(organization)
        await session.flush()
        engagement = EngagementModel(
            organization_id=organization.id, title="Analysis Integration Test Engagement"
        )
        session.add(engagement)
        await session.flush()
        document = DocumentModel(
            filename="report.pdf", storage_path=f"test/{uuid.uuid4()}.pdf",
            processing_status="PROCESSED", engagement_id=engagement.id,
        )
        session.add(document)
        await session.flush()
        chunk_models = [
            DocumentChunkModel(
                document_id=document.id, chunk_index=index, content=content,
                char_start=0, char_end=len(content),
            )
            for index, content in enumerate(chunk_contents)
        ]
        session.add_all(chunk_models)
        await session.flush()
        embedding_models = [
            DocumentChunkEmbeddingModel(
                chunk_id=chunk.id, document_id=document.id, engagement_id=engagement.id,
                organization_id=organization.id, provider="openai",
                model=settings.embedding_model, model_version=EMBEDDING_MODEL_VERSION,
                embedding_dimension=DIMENSION, embedding=_deterministic_vector(chunk.content),
                content_hash=hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
                status="COMPLETED",
            )
            for chunk in chunk_models
        ]
        session.add_all(embedding_models)
        await session.flush()
        profile_id = uuid.uuid4()
        session.add(
            UserModel(
                id=profile_id, organization_id=organization.id,
                full_name="Analysis Integration Test User",
                email=f"analysis-integration-{profile_id}@example.com", role=None,
            )
        )
        await session.commit()

    cleanup_ids["organizations"].append(organization.id)
    cleanup_ids["engagements"].append(engagement.id)
    cleanup_ids["documents"].append(document.id)
    cleanup_ids["users"].append(profile_id)
    cleanup_ids["chunks"].extend(chunk.id for chunk in chunk_models)
    cleanup_ids["embeddings"].extend(m.id for m in embedding_models)
    return organization.id, engagement.id, profile_id, document.id


def _token_for(private_key, real_verifier: SupabaseJWTVerifier, profile_id: uuid.UUID) -> str:
    return _make_token(
        private_key, kid="integration-test-kid",
        overrides={
            "sub": str(profile_id), "iss": real_verifier.issuer, "aud": real_verifier.audience,
        },
    )


async def _track_run_from_response(
    cleanup_ids: dict[str, list[uuid.UUID]], body: dict
) -> None:
    cleanup_ids["runs"].append(uuid.UUID(body["analysis_run_id"]))
    cleanup_ids["citations"].extend(uuid.UUID(c["id"]) for c in body["citations"])


# ---------------------------------------------------------------------------
# Real citation lineage
# ---------------------------------------------------------------------------


async def test_engagement_analysis_persists_real_citation_lineage(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]], fake_llm_gateway: FakeLLMGateway,
) -> None:
    private_key, _public_key = keypair
    _org, engagement_id, profile_id, document_id = (
        await _make_org_engagement_document_with_embedded_chunks(
            cleanup_ids, chunk_contents=["Scope 1 emissions decreased significantly."]
        )
    )
    token = _token_for(private_key, real_verifier, profile_id)
    headers = {"Authorization": f"Bearer {token}"}
    fake_llm_gateway._responses = [VALID_STRUCTURED_OUTPUT]

    response = await client.post(
        f"/api/v1/analysis/engagements/{engagement_id}/analyze",
        headers=headers,
        json={
            "analysis_type": "sustainability_summary",
            "query_text": "Scope 1 emissions decreased significantly.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    await _track_run_from_response(cleanup_ids, body)
    assert body["status"] == "COMPLETED"
    assert len(body["citations"]) == 1
    citation = body["citations"][0]
    assert citation["document_id"] == str(document_id)

    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(AnalysisSourceReferenceModel, uuid.UUID(citation["id"]))
        assert model is not None
        assert model.document_id == document_id
        assert model.engagement_id == engagement_id


# ---------------------------------------------------------------------------
# Cross-tenant exclusion
# ---------------------------------------------------------------------------


async def test_foreign_tenant_more_similar_chunk_never_included_in_analysis(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]], fake_llm_gateway: FakeLLMGateway,
) -> None:
    """Two tenants, deliberately identical content -- proves tenant B's
    equally-perfect-match chunk is never assembled into tenant A's
    context, even though it would rank as an equally strong match by raw
    vector distance alone."""
    private_key, _public_key = keypair
    identical_content = "Deliberately identical disclosure text for both tenants."
    _org_a, engagement_a, profile_a, _doc_a = (
        await _make_org_engagement_document_with_embedded_chunks(
            cleanup_ids, chunk_contents=[identical_content]
        )
    )
    _org_b, _engagement_b, _profile_b, _doc_b = (
        await _make_org_engagement_document_with_embedded_chunks(
            cleanup_ids, chunk_contents=[identical_content]
        )
    )
    token_a = _token_for(private_key, real_verifier, profile_a)
    fake_llm_gateway._responses = [VALID_STRUCTURED_OUTPUT]

    response = await client.post(
        f"/api/v1/analysis/engagements/{engagement_a}/analyze",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"analysis_type": "sustainability_summary", "query_text": identical_content},
    )

    assert response.status_code == 200
    body = response.json()
    await _track_run_from_response(cleanup_ids, body)
    assert len(body["citations"]) == 1
    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(
            AnalysisSourceReferenceModel, uuid.UUID(body["citations"][0]["id"])
        )
        assert model is not None
        assert model.engagement_id == engagement_a  # never tenant B's chunk


async def test_foreign_tenant_document_returns_404(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> None:
    private_key, _public_key = keypair
    _org_a, _eng_a, profile_a, _doc_a = await _make_org_engagement_document_with_embedded_chunks(
        cleanup_ids, chunk_contents=["Tenant A content."]
    )
    _org_b, _eng_b, _profile_b, document_b = await _make_org_engagement_document_with_embedded_chunks(
        cleanup_ids, chunk_contents=["Tenant B content."]
    )
    token_a = _token_for(private_key, real_verifier, profile_a)

    response = await client.post(
        f"/api/v1/analysis/documents/{document_b}/analyze",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"analysis_type": "sustainability_summary", "query_text": "q"},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Mandatory Correction 1 -- tenant-safe idempotency, end to end
# ---------------------------------------------------------------------------


async def test_identical_request_same_tenant_is_idempotent_end_to_end(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]], fake_llm_gateway: FakeLLMGateway,
) -> None:
    private_key, _public_key = keypair
    _org, engagement_id, profile_id, _doc = await _make_org_engagement_document_with_embedded_chunks(
        cleanup_ids, chunk_contents=["Scope 1 emissions decreased."]
    )
    token = _token_for(private_key, real_verifier, profile_id)
    headers = {"Authorization": f"Bearer {token}"}
    fake_llm_gateway._responses = [VALID_STRUCTURED_OUTPUT]
    payload = {
        "analysis_type": "sustainability_summary", "query_text": "Scope 1 emissions decreased.",
    }

    first = await client.post(
        f"/api/v1/analysis/engagements/{engagement_id}/analyze", headers=headers, json=payload
    )
    second = await client.post(
        f"/api/v1/analysis/engagements/{engagement_id}/analyze", headers=headers, json=payload
    )

    assert first.status_code == 200
    assert second.status_code == 200
    await _track_run_from_response(cleanup_ids, first.json())
    assert first.json()["analysis_run_id"] == second.json()["analysis_run_id"]
    assert fake_llm_gateway.call_count == 1  # the LLM was never called twice


async def test_identical_request_different_tenants_creates_separate_runs_end_to_end(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]], fake_llm_gateway: FakeLLMGateway,
) -> None:
    private_key, _public_key = keypair
    identical_content = "Identical content across two tenants."
    _org_a, engagement_a, profile_a, _doc_a = (
        await _make_org_engagement_document_with_embedded_chunks(
            cleanup_ids, chunk_contents=[identical_content]
        )
    )
    _org_b, engagement_b, profile_b, _doc_b = (
        await _make_org_engagement_document_with_embedded_chunks(
            cleanup_ids, chunk_contents=[identical_content]
        )
    )
    token_a = _token_for(private_key, real_verifier, profile_a)
    token_b = _token_for(private_key, real_verifier, profile_b)
    fake_llm_gateway._responses = [VALID_STRUCTURED_OUTPUT, VALID_STRUCTURED_OUTPUT]
    payload = {"analysis_type": "sustainability_summary", "query_text": identical_content}

    response_a = await client.post(
        f"/api/v1/analysis/engagements/{engagement_a}/analyze",
        headers={"Authorization": f"Bearer {token_a}"}, json=payload,
    )
    response_b = await client.post(
        f"/api/v1/analysis/engagements/{engagement_b}/analyze",
        headers={"Authorization": f"Bearer {token_b}"}, json=payload,
    )

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    await _track_run_from_response(cleanup_ids, response_a.json())
    await _track_run_from_response(cleanup_ids, response_b.json())
    assert response_a.json()["analysis_run_id"] != response_b.json()["analysis_run_id"]


async def test_failed_run_is_retried_on_next_request_end_to_end(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]], fake_llm_gateway: FakeLLMGateway,
) -> None:
    private_key, _public_key = keypair
    _org, engagement_id, profile_id, _doc = await _make_org_engagement_document_with_embedded_chunks(
        cleanup_ids, chunk_contents=["Scope 1 emissions decreased."]
    )
    token = _token_for(private_key, real_verifier, profile_id)
    headers = {"Authorization": f"Bearer {token}"}
    fake_llm_gateway._responses = [
        LLMProviderUnavailableError("temporary failure"), VALID_STRUCTURED_OUTPUT,
    ]
    payload = {
        "analysis_type": "sustainability_summary", "query_text": "Scope 1 emissions decreased.",
    }

    first = await client.post(
        f"/api/v1/analysis/engagements/{engagement_id}/analyze", headers=headers, json=payload
    )
    assert first.status_code == 200
    assert first.json()["status"] == "FAILED"
    await _track_run_from_response(cleanup_ids, first.json())

    second = await client.post(
        f"/api/v1/analysis/engagements/{engagement_id}/analyze", headers=headers, json=payload
    )

    assert second.status_code == 200
    assert second.json()["status"] == "COMPLETED"
    assert second.json()["analysis_run_id"] == first.json()["analysis_run_id"]
    await _track_run_from_response(cleanup_ids, second.json())


async def test_stale_processing_run_is_reclaimed_end_to_end(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]], fake_llm_gateway: FakeLLMGateway,
) -> None:
    """Simulates a previous request's process dying mid-flight by directly
    inserting a PROCESSING analysis_runs row (with the exact request_hash
    the real request below will compute) whose processing_started_at is
    already past the staleness threshold, then proving the real endpoint
    reclaims and completes it rather than treating it as still in flight."""
    private_key, _public_key = keypair
    _org, engagement_id, profile_id, _doc = await _make_org_engagement_document_with_embedded_chunks(
        cleanup_ids, chunk_contents=["Scope 1 emissions decreased."]
    )
    token = _token_for(private_key, real_verifier, profile_id)
    headers = {"Authorization": f"Bearer {token}"}
    settings = get_settings()

    from decimal import Decimal

    from app.services.analysis.request_hash import compute_request_hash

    async with AsyncSessionLocal() as session:
        organization = await session.get(OrganizationModel, _org)
        assert organization is not None
        request_hash = compute_request_hash(
            organization_id=_org,
            engagement_id=engagement_id,
            document_id=None,
            analysis_type="sustainability_summary",
            query_text="Scope 1 emissions decreased.",
            provider="openai",
            model=settings.openai_model,
            prompt_template_version=settings.rag_prompt_template_version,
            output_schema_version=settings.rag_output_schema_version,
            temperature=Decimal(str(settings.llm_temperature)),
            retrieval_top_k=settings.rag_retrieval_top_k,
            embedding_provider="openai",
            embedding_model=settings.embedding_model,
            embedding_model_version=EMBEDDING_MODEL_VERSION,
            minimum_relevance_score=Decimal(str(settings.rag_minimum_relevance_score)),
        )
        stale_run = AnalysisRunModel(
            organization_id=_org, engagement_id=engagement_id, document_id=None,
            requested_by_user_id=profile_id, analysis_type="sustainability_summary",
            query_text="Scope 1 emissions decreased.", provider="openai",
            model=settings.openai_model,
            prompt_template_version=settings.rag_prompt_template_version,
            output_schema_version=settings.rag_output_schema_version,
            temperature=Decimal(str(settings.llm_temperature)),
            retrieval_top_k=settings.rag_retrieval_top_k, embedding_provider="openai",
            embedding_model=settings.embedding_model,
            embedding_model_version=EMBEDDING_MODEL_VERSION,
            minimum_relevance_score=Decimal(str(settings.rag_minimum_relevance_score)),
            request_hash=request_hash, status="PROCESSING",
            processing_started_at=datetime.now(timezone.utc)
            - timedelta(seconds=settings.rag_processing_stale_after_seconds + 60),
        )
        session.add(stale_run)
        await session.commit()
        await session.refresh(stale_run)
    cleanup_ids["runs"].append(stale_run.id)

    fake_llm_gateway._responses = [VALID_STRUCTURED_OUTPUT]
    response = await client.post(
        f"/api/v1/analysis/engagements/{engagement_id}/analyze",
        headers=headers,
        json={
            "analysis_type": "sustainability_summary",
            "query_text": "Scope 1 emissions decreased.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_run_id"] == str(stale_run.id)
    assert body["status"] == "COMPLETED"
    cleanup_ids["citations"].extend(uuid.UUID(c["id"]) for c in body["citations"])


# ---------------------------------------------------------------------------
# Insufficient evidence
# ---------------------------------------------------------------------------


async def test_no_relevant_evidence_marks_insufficient_evidence_without_calling_llm(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]], fake_llm_gateway: FakeLLMGateway,
) -> None:
    private_key, _public_key = keypair
    _org, engagement_id, profile_id, _doc = await _make_org_engagement_document_with_embedded_chunks(
        cleanup_ids, chunk_contents=[]
    )
    token = _token_for(private_key, real_verifier, profile_id)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"/api/v1/analysis/engagements/{engagement_id}/analyze",
        headers=headers,
        json={"analysis_type": "sustainability_summary", "query_text": "anything"},
    )

    assert response.status_code == 200
    body = response.json()
    await _track_run_from_response(cleanup_ids, body)
    assert body["status"] == "INSUFFICIENT_EVIDENCE"
    assert fake_llm_gateway.call_count == 0
