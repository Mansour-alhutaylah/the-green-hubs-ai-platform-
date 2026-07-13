"""Focused end-to-end integration tests for the embedding generation and
vector retrieval endpoints, exercised through the real ``app`` against
the real database. The embedding *provider* is swapped for an in-memory
fake via ``dependency_overrides`` -- no live OpenAI call, matching this
project's existing "never call live external AI/network services in
tests" discipline. Real pgvector storage and real cosine-similarity
queries are exercised end-to-end.

Every row a test creates is tracked and cleaned up in dependency-safe
order: document_chunk_embeddings, then document_chunks, then documents,
then users, then engagements, then organizations, via an independent
session in teardown, regardless of test outcome.
"""

import hashlib
import uuid
from typing import AsyncIterator, Sequence

import pytest
from httpx import AsyncClient

from app.api.deps import get_embedding_provider, get_supabase_jwt_verifier
from app.core.config import get_settings
from app.domain.embedding_provider import EmbeddingProvider, EmbeddingResult
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


def _deterministic_vector(text: str) -> list[float]:
    """A cheap, deterministic 1536-dim vector derived from the text's hash
    -- close for near-identical inputs, far apart otherwise -- standing
    in for a real embedding without any network dependency."""
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
    return [((seed >> (i % 64)) % 1000) / 1000.0 for i in range(DIMENSION)]


class FakeEmbeddingProvider(EmbeddingProvider):
    async def embed_texts(self, texts: Sequence[str]) -> Sequence[EmbeddingResult]:
        return [
            EmbeddingResult(text=t, vector=_deterministic_vector(t), dimension=DIMENSION)
            for t in texts
        ]


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
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    yield
    app.dependency_overrides.pop(get_supabase_jwt_verifier, None)
    app.dependency_overrides.pop(get_embedding_provider, None)


@pytest.fixture
async def cleanup_ids() -> AsyncIterator[dict[str, list[uuid.UUID]]]:
    ids: dict[str, list[uuid.UUID]] = {
        "embeddings": [], "chunks": [], "documents": [], "users": [], "engagements": [],
        "organizations": [],
    }
    yield ids
    async with AsyncSessionLocal() as cleanup_session:
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


async def _make_org_engagement_document_with_chunks(
    cleanup_ids: dict[str, list[uuid.UUID]], *, chunk_contents: list[str]
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Returns (organization_id, engagement_id, profile_id, document_id)."""
    async with AsyncSessionLocal() as session:
        organization = OrganizationModel(name="Embedding Integration Test Org")
        session.add(organization)
        await session.flush()
        engagement = EngagementModel(
            organization_id=organization.id, title="Embedding Integration Test Engagement"
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
        profile_id = uuid.uuid4()
        session.add(
            UserModel(
                id=profile_id, organization_id=organization.id,
                full_name="Embedding Integration Test User",
                email=f"embedding-integration-{profile_id}@example.com", role=None,
            )
        )
        await session.commit()

    cleanup_ids["organizations"].append(organization.id)
    cleanup_ids["engagements"].append(engagement.id)
    cleanup_ids["documents"].append(document.id)
    cleanup_ids["users"].append(profile_id)
    cleanup_ids["chunks"].extend(chunk.id for chunk in chunk_models)
    return organization.id, engagement.id, profile_id, document.id


def _token_for(private_key, real_verifier: SupabaseJWTVerifier, profile_id: uuid.UUID) -> str:
    return _make_token(
        private_key, kid="integration-test-kid",
        overrides={
            "sub": str(profile_id), "iss": real_verifier.issuer, "aud": real_verifier.audience,
        },
    )


async def test_generate_then_retrieve_end_to_end(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> None:
    private_key, _public_key = keypair
    _org, _eng, profile_id, document_id = await _make_org_engagement_document_with_chunks(
        cleanup_ids, chunk_contents=["Scope 1 emissions decreased.", "Scope 2 emissions increased."]
    )
    token = _token_for(private_key, real_verifier, profile_id)
    headers = {"Authorization": f"Bearer {token}"}

    generate_response = await client.post(
        f"/api/v1/documents/{document_id}/embeddings", headers=headers
    )
    assert generate_response.status_code == 200
    summary = generate_response.json()
    assert summary["total_chunks"] == 2
    assert summary["newly_completed"] == 2
    assert summary["failed"] == 0

    async with AsyncSessionLocal() as verify_session:
        from sqlalchemy import select

        result = await verify_session.execute(
            select(DocumentChunkEmbeddingModel).where(
                DocumentChunkEmbeddingModel.document_id == document_id
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 2
        cleanup_ids["embeddings"].extend(r.id for r in rows)
        assert all(r.status == "COMPLETED" for r in rows)

    search_response = await client.post(
        "/api/v1/retrieval/search", headers=headers,
        json={"query": "Scope 1 emissions decreased.", "top_k": 5},
    )
    assert search_response.status_code == 200
    body = search_response.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["content"] == "Scope 1 emissions decreased."  # nearest match first
    assert "embedding" not in body["items"][0]


async def test_rerun_embeddings_is_idempotent(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> None:
    private_key, _public_key = keypair
    _org, _eng, profile_id, document_id = await _make_org_engagement_document_with_chunks(
        cleanup_ids, chunk_contents=["Single chunk content."]
    )
    token = _token_for(private_key, real_verifier, profile_id)
    headers = {"Authorization": f"Bearer {token}"}

    first_response = await client.post(
        f"/api/v1/documents/{document_id}/embeddings", headers=headers
    )
    assert first_response.status_code == 200
    assert first_response.json()["newly_completed"] == 1

    async with AsyncSessionLocal() as verify_session:
        from sqlalchemy import select

        result = await verify_session.execute(
            select(DocumentChunkEmbeddingModel).where(
                DocumentChunkEmbeddingModel.document_id == document_id
            )
        )
        rows = result.scalars().all()
        cleanup_ids["embeddings"].extend(r.id for r in rows)

    second_response = await client.post(
        f"/api/v1/documents/{document_id}/embeddings", headers=headers
    )

    assert second_response.status_code == 200
    body = second_response.json()
    assert body["newly_completed"] == 0
    assert body["already_completed"] == 1

    async with AsyncSessionLocal() as verify_session:
        from sqlalchemy import select

        result = await verify_session.execute(
            select(DocumentChunkEmbeddingModel).where(
                DocumentChunkEmbeddingModel.document_id == document_id
            )
        )
        rows_after = result.scalars().all()
        assert len(rows_after) == 1  # no duplicate row created


async def test_unprocessed_document_returns_409(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> None:
    private_key, _public_key = keypair
    async with AsyncSessionLocal() as session:
        organization = OrganizationModel(name="Unprocessed Doc Test Org")
        session.add(organization)
        await session.flush()
        engagement = EngagementModel(
            organization_id=organization.id, title="Unprocessed Doc Test Engagement"
        )
        session.add(engagement)
        await session.flush()
        document = DocumentModel(
            filename="report.pdf", storage_path=f"test/{uuid.uuid4()}.pdf",
            processing_status="PENDING", engagement_id=engagement.id,
        )
        session.add(document)
        profile_id = uuid.uuid4()
        session.add(
            UserModel(
                id=profile_id, organization_id=organization.id, full_name="Test User",
                email=f"unprocessed-{profile_id}@example.com", role=None,
            )
        )
        await session.commit()
    cleanup_ids["organizations"].append(organization.id)
    cleanup_ids["engagements"].append(engagement.id)
    cleanup_ids["documents"].append(document.id)
    cleanup_ids["users"].append(profile_id)

    token = _token_for(private_key, real_verifier, profile_id)
    response = await client.post(
        f"/api/v1/documents/{document.id}/embeddings",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409


async def test_cross_tenant_search_never_returns_the_other_organizations_nearest_match(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> None:
    private_key, _public_key = keypair
    identical_content = "Deliberately identical disclosure text for both tenants."
    _org_a, _eng_a, profile_a, document_a = await _make_org_engagement_document_with_chunks(
        cleanup_ids, chunk_contents=[identical_content]
    )
    _org_b, _eng_b, profile_b, document_b = await _make_org_engagement_document_with_chunks(
        cleanup_ids, chunk_contents=[identical_content]
    )
    token_a = _token_for(private_key, real_verifier, profile_a)
    token_b = _token_for(private_key, real_verifier, profile_b)

    for token, document_id in ((token_a, document_a), (token_b, document_b)):
        response = await client.post(
            f"/api/v1/documents/{document_id}/embeddings",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    async with AsyncSessionLocal() as verify_session:
        from sqlalchemy import select

        result = await verify_session.execute(
            select(DocumentChunkEmbeddingModel).where(
                DocumentChunkEmbeddingModel.document_id.in_([document_a, document_b])
            )
        )
        cleanup_ids["embeddings"].extend(r.id for r in result.scalars().all())

    search_response = await client.post(
        "/api/v1/retrieval/search",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"query": identical_content, "top_k": 10},
    )

    assert search_response.status_code == 200
    body = search_response.json()
    returned_document_ids = {item["document_id"] for item in body["items"]}
    assert str(document_a) in returned_document_ids
    assert str(document_b) not in returned_document_ids
