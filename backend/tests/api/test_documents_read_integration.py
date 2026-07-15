"""Integration API tests for the Document list/detail read endpoints.

Exercises the real orchestration path -- a real ``DocumentReadService``
wired with the real ``IDocumentRepository``/``IEngagementRepository``
against the configured database. No storage or provider dependency
exists on this read path, so nothing needs faking beyond the JWT
verifier's JWKS fetch (same technique as every other integration test
in this suite).

Two full tenants (Organization A / Organization B, one User each) are
created for every cross-tenant test. Every row a test creates --
``document_chunk_embeddings``, ``analysis_runs``, ``document_chunks``,
``extracted_text``, ``documents``, ``users``, ``engagements``,
``organizations`` -- is tracked and deleted in dependency-safe order in
``cleanup_ids``'s teardown, regardless of test outcome, then verified
gone.

Marked ``integration`` module-wide, mirroring
``test_documents_integration.py``.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

import pytest
from httpx import AsyncClient

from app.api.deps import get_supabase_jwt_verifier
from app.core.config import get_settings
from app.infrastructure.db.models.analysis_run import AnalysisRunModel
from app.infrastructure.db.models.document import DocumentModel
from app.infrastructure.db.models.document_chunk import DocumentChunkModel
from app.infrastructure.db.models.document_chunk_embedding import DocumentChunkEmbeddingModel
from app.infrastructure.db.models.engagement import Engagement as EngagementModel
from app.infrastructure.db.models.extracted_text import ExtractedText as ExtractedTextModel
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


class Ids:
    def __init__(self) -> None:
        self.embeddings: list[uuid.UUID] = []
        self.analysis_runs: list[uuid.UUID] = []
        self.chunks: list[uuid.UUID] = []
        self.extracted_text: list[uuid.UUID] = []
        self.documents: list[uuid.UUID] = []
        self.users: list[uuid.UUID] = []
        self.engagements: list[uuid.UUID] = []
        self.organizations: list[uuid.UUID] = []


@pytest.fixture
async def ids() -> AsyncIterator[Ids]:
    tracked = Ids()
    yield tracked
    async with AsyncSessionLocal() as session:
        for model_cls, id_list in (
            (DocumentChunkEmbeddingModel, tracked.embeddings),
            (AnalysisRunModel, tracked.analysis_runs),
            (DocumentChunkModel, tracked.chunks),
            (ExtractedTextModel, tracked.extracted_text),
            (DocumentModel, tracked.documents),
            (UserModel, tracked.users),
            (EngagementModel, tracked.engagements),
            (OrganizationModel, tracked.organizations),
        ):
            for row_id in id_list:
                model = await session.get(model_cls, row_id)
                if model is not None:
                    await session.delete(model)
            await session.commit()


async def _make_tenant(ids: Ids, *, name: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Creates an Organization + Engagement + matching ``public.users``
    profile. Returns (organization_id, engagement_id, profile_id)."""
    async with AsyncSessionLocal() as session:
        organization = OrganizationModel(name=name)
        session.add(organization)
        await session.flush()
        ids.organizations.append(organization.id)

        engagement = EngagementModel(organization_id=organization.id, title=f"{name} Engagement")
        session.add(engagement)
        await session.flush()
        ids.engagements.append(engagement.id)

        profile_id = uuid.uuid4()
        profile = UserModel(
            id=profile_id,
            organization_id=organization.id,
            full_name=f"{name} User",
            email=f"{name.lower().replace(' ', '-')}-{profile_id}@example.com",
            role="admin",
        )
        session.add(profile)
        await session.commit()
        ids.users.append(profile_id)

        return organization.id, engagement.id, profile_id


async def _make_document(
    ids: Ids,
    *,
    engagement_id: uuid.UUID,
    filename: str = "report.pdf",
    processing_status: str = "PROCESSED",
    created_at: datetime | None = None,
) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        model = DocumentModel(
            id=uuid.uuid4(),
            filename=filename,
            storage_path=f"test/{uuid.uuid4()}.pdf",
            processing_status=processing_status,
            engagement_id=engagement_id,
        )
        session.add(model)
        await session.commit()
        if created_at is not None:
            # created_at has a server_default; overwrite it directly via a
            # raw UPDATE so ordering tests can control it deterministically.
            from sqlalchemy import update

            await session.execute(
                update(DocumentModel).where(DocumentModel.id == model.id).values(created_at=created_at)
            )
            await session.commit()
        ids.documents.append(model.id)
        return model.id


async def _add_extracted_text(ids: Ids, *, document_id: uuid.UUID, content: str = "Some extracted content") -> None:
    async with AsyncSessionLocal() as session:
        model = ExtractedTextModel(document_id=document_id, extracted_content=content)
        session.add(model)
        await session.commit()
        ids.extracted_text.append(model.id)


async def _add_chunks(ids: Ids, *, document_id: uuid.UUID, count: int) -> list[uuid.UUID]:
    chunk_ids: list[uuid.UUID] = []
    async with AsyncSessionLocal() as session:
        for index in range(count):
            model = DocumentChunkModel(
                document_id=document_id,
                chunk_index=index,
                content=f"chunk {index}",
                char_start=index * 100,
                char_end=(index + 1) * 100,
            )
            session.add(model)
            await session.flush()
            chunk_ids.append(model.id)
            ids.chunks.append(model.id)
        await session.commit()
    return chunk_ids


async def _add_embedding(
    ids: Ids,
    *,
    chunk_id: uuid.UUID,
    document_id: uuid.UUID,
    engagement_id: uuid.UUID,
    organization_id: uuid.UUID,
    status: str,
) -> None:
    content_hash = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()
    embedding = [0.0] * 1536 if status == "COMPLETED" else None
    error_message = "embedding provider failure" if status == "FAILED" else None
    async with AsyncSessionLocal() as session:
        model = DocumentChunkEmbeddingModel(
            chunk_id=chunk_id,
            document_id=document_id,
            engagement_id=engagement_id,
            organization_id=organization_id,
            provider="openai",
            model="text-embedding-3-small",
            model_version="",
            embedding_dimension=1536,
            embedding=embedding,
            content_hash=content_hash,
            status=status,
            error_message=error_message,
        )
        session.add(model)
        await session.commit()
        ids.embeddings.append(model.id)


async def _add_analysis_run(
    ids: Ids,
    *,
    organization_id: uuid.UUID,
    engagement_id: uuid.UUID,
    document_id: uuid.UUID,
    requested_by_user_id: uuid.UUID,
    status: str = "COMPLETED",
    overall_confidence: float | None = 0.75,
    created_at: datetime | None = None,
) -> uuid.UUID:
    request_hash = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()
    structured_output = None
    error_message = None
    insufficient_evidence_reason = None
    completed_at = None
    if status == "COMPLETED":
        structured_output = {
            "analysis_type": "sustainability_summary",
            "evidence_status": "sufficient",
            "executive_summary": "Summary",
            "overall_confidence": overall_confidence,
        }
        completed_at = datetime.now(timezone.utc)
    elif status == "FAILED":
        error_message = "analysis failure"
    elif status == "INSUFFICIENT_EVIDENCE":
        insufficient_evidence_reason = "not enough evidence"
        completed_at = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        model = AnalysisRunModel(
            organization_id=organization_id,
            engagement_id=engagement_id,
            document_id=document_id,
            requested_by_user_id=requested_by_user_id,
            analysis_type="sustainability_summary",
            query_text="What are the key metrics?",
            provider="openai",
            model="gpt-test",
            prompt_template_version="v1",
            output_schema_version="v1",
            temperature=0.0,
            retrieval_top_k=5,
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
            embedding_model_version="",
            minimum_relevance_score=0.0,
            request_hash=request_hash,
            status=status,
            structured_output=structured_output,
            error_message=error_message,
            insufficient_evidence_reason=insufficient_evidence_reason,
            completed_at=completed_at,
        )
        session.add(model)
        await session.commit()
        if created_at is not None:
            from sqlalchemy import update

            await session.execute(
                update(AnalysisRunModel).where(AnalysisRunModel.id == model.id).values(created_at=created_at)
            )
            await session.commit()
        ids.analysis_runs.append(model.id)
        return model.id


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


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


async def test_organization_a_cannot_list_organization_bs_documents(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier, ids: Ids
) -> None:
    private_key, _public_key = keypair
    _org_a, _eng_a, user_a = await _make_tenant(ids, name="Doc Read List A")
    _org_b, eng_b, _user_b = await _make_tenant(ids, name="Doc Read List B")
    await _make_document(ids, engagement_id=eng_b)

    token = _token_for(private_key, real_verifier, user_a)
    response = await client.get("/api/v1/documents", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


async def test_organization_a_cannot_fetch_organization_bs_document_detail(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier, ids: Ids
) -> None:
    private_key, _public_key = keypair
    _org_a, _eng_a, user_a = await _make_tenant(ids, name="Doc Read Detail A")
    _org_b, eng_b, _user_b = await _make_tenant(ids, name="Doc Read Detail B")
    document_id = await _make_document(ids, engagement_id=eng_b)

    token = _token_for(private_key, real_verifier, user_a)
    response = await client.get(
        f"/api/v1/documents/{document_id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


async def test_foreign_engagement_filter_returns_404(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier, ids: Ids
) -> None:
    private_key, _public_key = keypair
    _org_a, _eng_a, user_a = await _make_tenant(ids, name="Doc Read Foreign Eng A")
    _org_b, eng_b, _user_b = await _make_tenant(ids, name="Doc Read Foreign Eng B")

    token = _token_for(private_key, real_verifier, user_a)
    response = await client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        params={"engagement_id": str(eng_b)},
    )

    assert response.status_code == 404


async def test_foreign_document_returns_404(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier, ids: Ids
) -> None:
    private_key, _public_key = keypair
    _org_a, _eng_a, user_a = await _make_tenant(ids, name="Doc Read Foreign Doc A")

    token = _token_for(private_key, real_verifier, user_a)
    response = await client.get(
        f"/api/v1/documents/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


async def test_client_supplied_organization_id_does_not_change_scope(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier, ids: Ids
) -> None:
    private_key, _public_key = keypair
    org_a, eng_a, user_a = await _make_tenant(ids, name="Doc Read Org Param A")
    org_b, eng_b, _user_b = await _make_tenant(ids, name="Doc Read Org Param B")
    await _make_document(ids, engagement_id=eng_a)
    await _make_document(ids, engagement_id=eng_b)

    token = _token_for(private_key, real_verifier, user_a)
    response = await client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        params={"organization_id": str(org_b)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["engagement_id"] == str(eng_a)


async def test_foreign_tenants_more_recent_analysis_never_appears_in_summary(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier, ids: Ids
) -> None:
    private_key, _public_key = keypair
    org_a, eng_a, user_a = await _make_tenant(ids, name="Doc Read Foreign Analysis A")
    org_b, eng_b, user_b = await _make_tenant(ids, name="Doc Read Foreign Analysis B")

    document_a = await _make_document(ids, engagement_id=eng_a)
    document_b = await _make_document(ids, engagement_id=eng_b)

    now = datetime.now(timezone.utc)
    await _add_analysis_run(
        ids,
        organization_id=org_a,
        engagement_id=eng_a,
        document_id=document_a,
        requested_by_user_id=user_a,
        overall_confidence=0.5,
        created_at=now - timedelta(days=1),
    )
    # Organization B's run is more recent and targets a different document,
    # but shares nothing tenant-wise with A -- it must never leak into A's view.
    await _add_analysis_run(
        ids,
        organization_id=org_b,
        engagement_id=eng_b,
        document_id=document_b,
        requested_by_user_id=user_b,
        overall_confidence=0.99,
        created_at=now,
    )

    token = _token_for(private_key, real_verifier, user_a)
    response = await client.get(
        f"/api/v1/documents/{document_a}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    summary = response.json()["latest_analysis_summary"]
    assert summary is not None
    assert summary["overall_confidence"] == 0.5


async def test_foreign_tenants_embeddings_do_not_affect_counts(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier, ids: Ids
) -> None:
    private_key, _public_key = keypair
    org_a, eng_a, user_a = await _make_tenant(ids, name="Doc Read Foreign Embed A")
    org_b, eng_b, _user_b = await _make_tenant(ids, name="Doc Read Foreign Embed B")

    document_a = await _make_document(ids, engagement_id=eng_a)
    chunks_a = await _add_chunks(ids, document_id=document_a, count=2)
    for chunk_id in chunks_a:
        await _add_embedding(
            ids,
            chunk_id=chunk_id,
            document_id=document_a,
            engagement_id=eng_a,
            organization_id=org_a,
            status="COMPLETED",
        )

    document_b = await _make_document(ids, engagement_id=eng_b)
    chunks_b = await _add_chunks(ids, document_id=document_b, count=5)
    for chunk_id in chunks_b:
        await _add_embedding(
            ids,
            chunk_id=chunk_id,
            document_id=document_b,
            engagement_id=eng_b,
            organization_id=org_b,
            status="FAILED",
        )

    token = _token_for(private_key, real_verifier, user_a)
    response = await client.get(
        f"/api/v1/documents/{document_a}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    summary = response.json()["embedding_summary"]
    assert summary["total_chunks"] == 2
    assert summary["completed"] == 2
    assert summary["failed"] == 0
    assert summary["is_complete"] is True


# ---------------------------------------------------------------------------
# Filtering, pagination, ordering
# ---------------------------------------------------------------------------


async def test_engagement_filter_returns_only_matching_documents(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier, ids: Ids
) -> None:
    private_key, _public_key = keypair
    org_a, eng_1, user_a = await _make_tenant(ids, name="Doc Read Eng Filter A")
    async with AsyncSessionLocal() as session:
        other_engagement = EngagementModel(organization_id=org_a, title="Second Engagement")
        session.add(other_engagement)
        await session.commit()
        ids.engagements.append(other_engagement.id)
    eng_2 = other_engagement.id

    await _make_document(ids, engagement_id=eng_1)
    await _make_document(ids, engagement_id=eng_2)

    token = _token_for(private_key, real_verifier, user_a)
    response = await client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        params={"engagement_id": str(eng_1)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["engagement_id"] == str(eng_1)


async def test_processing_status_filter_returns_only_matching_documents(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier, ids: Ids
) -> None:
    private_key, _public_key = keypair
    _org_a, eng_a, user_a = await _make_tenant(ids, name="Doc Read Status Filter A")
    await _make_document(ids, engagement_id=eng_a, processing_status="PENDING")
    await _make_document(ids, engagement_id=eng_a, processing_status="FAILED")

    token = _token_for(private_key, real_verifier, user_a)
    response = await client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        params={"processing_status": "FAILED"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["processing_status"] == "FAILED"


async def test_pagination_and_total_count(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier, ids: Ids
) -> None:
    private_key, _public_key = keypair
    _org_a, eng_a, user_a = await _make_tenant(ids, name="Doc Read Pagination A")
    for _ in range(5):
        await _make_document(ids, engagement_id=eng_a)

    token = _token_for(private_key, real_verifier, user_a)
    headers = {"Authorization": f"Bearer {token}"}

    first_page = await client.get("/api/v1/documents", headers=headers, params={"limit": 2, "offset": 0})
    second_page = await client.get("/api/v1/documents", headers=headers, params={"limit": 2, "offset": 2})

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert first_page.json()["total"] == 5
    assert second_page.json()["total"] == 5
    assert len(first_page.json()["items"]) == 2
    assert len(second_page.json()["items"]) == 2
    first_ids = {item["id"] for item in first_page.json()["items"]}
    second_ids = {item["id"] for item in second_page.json()["items"]}
    assert first_ids.isdisjoint(second_ids)


async def test_newest_first_deterministic_order(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier, ids: Ids
) -> None:
    private_key, _public_key = keypair
    _org_a, eng_a, user_a = await _make_tenant(ids, name="Doc Read Ordering A")
    now = datetime.now(timezone.utc)
    older = await _make_document(ids, engagement_id=eng_a, created_at=now - timedelta(hours=2))
    newer = await _make_document(ids, engagement_id=eng_a, created_at=now - timedelta(hours=1))

    token = _token_for(private_key, real_verifier, user_a)
    response = await client.get(
        "/api/v1/documents", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    ids_in_order = [item["id"] for item in response.json()["items"]]
    assert ids_in_order.index(str(newer)) < ids_in_order.index(str(older))


# ---------------------------------------------------------------------------
# Derived fields
# ---------------------------------------------------------------------------


async def test_has_extracted_text_reflects_real_availability(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier, ids: Ids
) -> None:
    private_key, _public_key = keypair
    _org_a, eng_a, user_a = await _make_tenant(ids, name="Doc Read Extracted Text A")
    with_text = await _make_document(ids, engagement_id=eng_a)
    await _add_extracted_text(ids, document_id=with_text)
    without_text = await _make_document(ids, engagement_id=eng_a)

    token = _token_for(private_key, real_verifier, user_a)
    headers = {"Authorization": f"Bearer {token}"}

    response_with = await client.get(f"/api/v1/documents/{with_text}", headers=headers)
    response_without = await client.get(f"/api/v1/documents/{without_text}", headers=headers)

    assert response_with.json()["has_extracted_text"] is True
    assert response_without.json()["has_extracted_text"] is False


async def test_chunk_count_reflects_real_document_chunks(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier, ids: Ids
) -> None:
    private_key, _public_key = keypair
    _org_a, eng_a, user_a = await _make_tenant(ids, name="Doc Read Chunk Count A")
    document_id = await _make_document(ids, engagement_id=eng_a)
    await _add_chunks(ids, document_id=document_id, count=7)

    token = _token_for(private_key, real_verifier, user_a)
    response = await client.get(
        f"/api/v1/documents/{document_id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.json()["chunk_count"] == 7


async def test_embedding_summary_reflects_mixed_statuses(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier, ids: Ids
) -> None:
    private_key, _public_key = keypair
    org_a, eng_a, user_a = await _make_tenant(ids, name="Doc Read Embed Summary A")
    document_id = await _make_document(ids, engagement_id=eng_a)
    chunk_ids = await _add_chunks(ids, document_id=document_id, count=3)
    await _add_embedding(
        ids, chunk_id=chunk_ids[0], document_id=document_id, engagement_id=eng_a,
        organization_id=org_a, status="COMPLETED",
    )
    await _add_embedding(
        ids, chunk_id=chunk_ids[1], document_id=document_id, engagement_id=eng_a,
        organization_id=org_a, status="FAILED",
    )
    await _add_embedding(
        ids, chunk_id=chunk_ids[2], document_id=document_id, engagement_id=eng_a,
        organization_id=org_a, status="PROCESSING",
    )

    token = _token_for(private_key, real_verifier, user_a)
    response = await client.get(
        f"/api/v1/documents/{document_id}", headers={"Authorization": f"Bearer {token}"}
    )

    summary = response.json()["embedding_summary"]
    assert summary["total_chunks"] == 3
    assert summary["completed"] == 1
    assert summary["failed"] == 1
    assert summary["processing"] == 1
    assert summary["is_complete"] is False


async def test_latest_analysis_summary_picks_most_recent_run(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier, ids: Ids
) -> None:
    private_key, _public_key = keypair
    org_a, eng_a, user_a = await _make_tenant(ids, name="Doc Read Latest Analysis A")
    document_id = await _make_document(ids, engagement_id=eng_a)
    now = datetime.now(timezone.utc)
    await _add_analysis_run(
        ids, organization_id=org_a, engagement_id=eng_a, document_id=document_id,
        requested_by_user_id=user_a, overall_confidence=0.2, created_at=now - timedelta(hours=2),
    )
    latest_id = await _add_analysis_run(
        ids, organization_id=org_a, engagement_id=eng_a, document_id=document_id,
        requested_by_user_id=user_a, overall_confidence=0.95, created_at=now - timedelta(hours=1),
    )

    token = _token_for(private_key, real_verifier, user_a)
    response = await client.get(
        f"/api/v1/documents/{document_id}", headers={"Authorization": f"Bearer {token}"}
    )

    summary = response.json()["latest_analysis_summary"]
    assert summary is not None
    assert summary["id"] == str(latest_id)
    assert summary["overall_confidence"] == 0.95


async def test_document_with_no_analysis_returns_null_summary(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier, ids: Ids
) -> None:
    private_key, _public_key = keypair
    _org_a, eng_a, user_a = await _make_tenant(ids, name="Doc Read No Analysis A")
    document_id = await _make_document(ids, engagement_id=eng_a)

    token = _token_for(private_key, real_verifier, user_a)
    response = await client.get(
        f"/api/v1/documents/{document_id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.json()["latest_analysis_summary"] is None


# ---------------------------------------------------------------------------
# Cleanup verification
# ---------------------------------------------------------------------------


async def test_cleanup_removes_every_row_this_suite_creates(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier
) -> None:
    """Builds a full row set (org, engagement, user, document, extracted
    text, chunk, embedding, analysis run) via a locally-scoped ``Ids``
    that is *not* the ``ids`` fixture, so this test controls teardown
    timing itself: it proves every row exists after the request
    succeeds, deletes them the same way the ``ids`` fixture does, then
    proves none remain -- a genuine before/after check, not reliance on
    a fixture teardown this test can't observe."""
    local_ids = Ids()
    private_key, _public_key = keypair
    org_a, eng_a, user_a = await _make_tenant(local_ids, name="Doc Read Cleanup A")
    document_id = await _make_document(local_ids, engagement_id=eng_a)
    await _add_extracted_text(local_ids, document_id=document_id)
    chunk_ids = await _add_chunks(local_ids, document_id=document_id, count=1)
    await _add_embedding(
        local_ids, chunk_id=chunk_ids[0], document_id=document_id, engagement_id=eng_a,
        organization_id=org_a, status="COMPLETED",
    )
    await _add_analysis_run(
        local_ids, organization_id=org_a, engagement_id=eng_a, document_id=document_id,
        requested_by_user_id=user_a,
    )

    token = _token_for(private_key, real_verifier, user_a)
    response = await client.get(
        f"/api/v1/documents/{document_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200

    ordered_tables = (
        (DocumentChunkEmbeddingModel, local_ids.embeddings),
        (AnalysisRunModel, local_ids.analysis_runs),
        (DocumentChunkModel, local_ids.chunks),
        (ExtractedTextModel, local_ids.extracted_text),
        (DocumentModel, local_ids.documents),
        (UserModel, local_ids.users),
        (EngagementModel, local_ids.engagements),
        (OrganizationModel, local_ids.organizations),
    )

    async with AsyncSessionLocal() as verify_session:
        for model_cls, id_list in ordered_tables:
            for row_id in id_list:
                model = await verify_session.get(model_cls, row_id)
                assert model is not None, f"expected {model_cls.__name__} {row_id} to exist"

    async with AsyncSessionLocal() as cleanup_session:
        for model_cls, id_list in ordered_tables:
            for row_id in id_list:
                model = await cleanup_session.get(model_cls, row_id)
                if model is not None:
                    await cleanup_session.delete(model)
            await cleanup_session.commit()

    async with AsyncSessionLocal() as verify_session:
        for model_cls, id_list in ordered_tables:
            for row_id in id_list:
                assert await verify_session.get(model_cls, row_id) is None
