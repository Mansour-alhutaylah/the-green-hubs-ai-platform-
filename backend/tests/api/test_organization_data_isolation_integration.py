"""MVP Slice 3 -- the cross-tenant negative matrix, end to end.

Every test here builds **two complete tenants** against the real database:
Organization A with User A and its own rows, Organization B with User B
and its own rows. User A then attacks Organization B's rows using their
**real, valid UUIDs**, read straight out of the database.

That distinction is the entire point of this module. A test that requests
``uuid4()`` and asserts 404 proves only that unknown ids are unknown -- it
would pass just as happily against a completely unscoped repository,
because the row genuinely does not exist. Only a *real* foreign UUID
distinguishes "this query is tenant-scoped" from "this row happened not to
be there", and only that shape can catch a regression that drops an
``organization_id`` predicate.

Each test also asserts the negative side-effect where one exists: the
victim's row is unchanged, no storage object was written or read, and no
child row (embedding, analysis run) was created against their data. A 404
whose write already landed is not isolation.

Scope note: this module covers the tenant boundary only. Permission
checks (Slice 2) are exercised in ``test_authorization.py`` and are
deliberately not re-tested here -- both users below are ``admin``, so
every request that gets rejected is rejected for tenancy, not for role.

External providers (embeddings, LLM) and object storage are replaced with
in-memory fakes via ``dependency_overrides``, matching every other
integration module in this suite; the database, its joins and pgvector are
real. Every row created is tracked and removed in dependency-safe order in
``cleanup_ids``'s teardown regardless of outcome.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import AsyncIterator, Sequence

import pytest
from httpx import AsyncClient

from app.api.deps import (
    get_document_storage,
    get_embedding_provider,
    get_llm_gateway,
    get_supabase_jwt_verifier,
)
from app.core.config import get_settings
from app.domain.embedding_provider import EmbeddingProvider, EmbeddingResult
from app.domain.llm_gateway import LLMGateway, LLMStructuredResult
from app.domain.storage.document_storage import IDocumentStorage, StorageObjectNotFoundError
from app.infrastructure.db.models.analysis_run import AnalysisRunModel
from app.infrastructure.db.models.analysis_source_reference import AnalysisSourceReferenceModel
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

DIMENSION = 1536

# Both tenants' chunks contain this word, so a retrieval query for it is
# genuinely capable of matching either organization's vectors. If the
# tenant predicate were dropped, Organization B's chunk would rank and be
# returned -- which is exactly what the retrieval tests below detect.
SHARED_TOPIC = "scope 1 greenhouse gas emissions intensity"


def _deterministic_vector(text: str) -> list[float]:
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
    return [((seed >> (i % 64)) % 1000) / 1000.0 for i in range(DIMENSION)]


class FakeEmbeddingProvider(EmbeddingProvider):
    async def embed_texts(self, texts: Sequence[str]) -> Sequence[EmbeddingResult]:
        return [
            EmbeddingResult(text=t, vector=_deterministic_vector(t), dimension=DIMENSION)
            for t in texts
        ]


class FakeLLMGateway(LLMGateway):
    def __init__(self) -> None:
        self.call_count = 0

    async def complete_structured(
        self, *, system_prompt: str, user_prompt: str, validator=None
    ) -> LLMStructuredResult:
        self.call_count += 1
        payload = {
            "analysis_type": "sustainability_summary",
            "evidence_status": "sufficient",
            "executive_summary": "Summary.",
            "overall_confidence": 0.9,
            "reported_metrics": [],
            "key_findings": [],
            "recommendations": [],
        }
        return LLMStructuredResult(
            raw_text=json.dumps(payload), parsed=payload, prompt_tokens=10,
            completion_tokens=20, total_tokens=30, model="gpt-4o-mini", finish_reason="stop",
        )


class FakeDocumentStorage(IDocumentStorage):
    """Records every call so a cross-tenant test can prove the attacker's
    request never touched the object store at all."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.put_calls: list[str] = []
        self.get_calls: list[str] = []
        self.delete_calls: list[str] = []

    def seed(self, object_key: str, content: bytes) -> None:
        self.objects[object_key] = content

    async def put(self, object_key: str, content: bytes, content_type: str) -> None:
        self.put_calls.append(object_key)
        self.objects[object_key] = content

    async def get(self, object_key: str) -> bytes:
        self.get_calls.append(object_key)
        if object_key not in self.objects:
            raise StorageObjectNotFoundError(object_key)
        return self.objects[object_key]

    async def delete(self, object_key: str) -> None:
        self.delete_calls.append(object_key)
        self.objects.pop(object_key, None)


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
def fake_storage() -> FakeDocumentStorage:
    return FakeDocumentStorage()


@pytest.fixture
def fake_llm_gateway() -> FakeLLMGateway:
    return FakeLLMGateway()


@pytest.fixture(autouse=True)
def _override_dependencies(
    keypair,
    real_verifier: SupabaseJWTVerifier,
    fake_storage: FakeDocumentStorage,
    fake_llm_gateway: FakeLLMGateway,
):
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
    app.dependency_overrides[get_document_storage] = lambda: fake_storage
    yield
    for dependency in (
        get_supabase_jwt_verifier,
        get_embedding_provider,
        get_llm_gateway,
        get_document_storage,
    ):
        app.dependency_overrides.pop(dependency, None)


class Ids:
    def __init__(self) -> None:
        self.citations: list[uuid.UUID] = []
        self.runs: list[uuid.UUID] = []
        self.embeddings: list[uuid.UUID] = []
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
            (AnalysisSourceReferenceModel, tracked.citations),
            (AnalysisRunModel, tracked.runs),
            (DocumentChunkEmbeddingModel, tracked.embeddings),
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


@dataclass
class Tenant:
    """One complete, self-contained organization."""

    organization_id: uuid.UUID
    engagement_id: uuid.UUID
    user_id: uuid.UUID
    document_id: uuid.UUID
    chunk_ids: list[uuid.UUID]
    storage_path: str
    token: str


async def _create_tenant(
    ids: Ids,
    private_key,
    real_verifier: SupabaseJWTVerifier,
    fake_storage: FakeDocumentStorage,
    *,
    label: str,
    role: str = "admin",
    with_organization: bool = True,
) -> Tenant:
    """Create Organization + Engagement + User + a PROCESSED Document with
    two chunks, and return every real id plus a signed token for the user."""

    async with AsyncSessionLocal() as session:
        organization = OrganizationModel(name=f"Slice3 Isolation {label}")
        session.add(organization)
        await session.flush()
        ids.organizations.append(organization.id)

        engagement = EngagementModel(
            organization_id=organization.id, title=f"Slice3 Isolation {label} Engagement"
        )
        session.add(engagement)
        await session.flush()
        ids.engagements.append(engagement.id)

        user_id = uuid.uuid4()
        session.add(
            UserModel(
                id=user_id,
                organization_id=organization.id if with_organization else None,
                full_name=f"Slice3 Isolation {label} User",
                email=f"slice3-{label.lower()}-{user_id}@example.com",
                role=role,
            )
        )
        ids.users.append(user_id)

        storage_path = (
            f"organizations/{organization.id}/engagements/{engagement.id}"
            f"/documents/{uuid.uuid4()}.pdf"
        )
        document = DocumentModel(
            id=uuid.uuid4(),
            filename=f"{label.lower()}-confidential-report.pdf",
            storage_path=storage_path,
            processing_status="PROCESSED",
            engagement_id=engagement.id,
        )
        session.add(document)
        await session.flush()
        ids.documents.append(document.id)

        chunk_ids: list[uuid.UUID] = []
        for index, content in enumerate(
            [
                f"{label} confidential: {SHARED_TOPIC} totalled 12,345 tCO2e.",
                f"{label} confidential: {SHARED_TOPIC} target is net zero by 2040.",
            ]
        ):
            chunk = DocumentChunkModel(
                document_id=document.id, chunk_index=index, content=content,
                char_start=0, char_end=len(content),
            )
            session.add(chunk)
            await session.flush()
            chunk_ids.append(chunk.id)
            ids.chunks.append(chunk.id)

        await session.commit()

    fake_storage.seed(storage_path, b"%PDF-1.4 fake bytes")

    token = _make_token(
        private_key,
        kid="integration-test-kid",
        overrides={
            "sub": str(user_id),
            "iss": real_verifier.issuer,
            "aud": real_verifier.audience,
        },
    )
    return Tenant(
        organization_id=organization.id,
        engagement_id=engagement.id,
        user_id=user_id,
        document_id=document.id,
        chunk_ids=chunk_ids,
        storage_path=storage_path,
        token=token,
    )


@pytest.fixture
async def tenants(
    ids: Ids, keypair, real_verifier: SupabaseJWTVerifier, fake_storage: FakeDocumentStorage
) -> tuple[Tenant, Tenant]:
    private_key, _public_key = keypair
    a = await _create_tenant(ids, private_key, real_verifier, fake_storage, label="OrgA")
    b = await _create_tenant(ids, private_key, real_verifier, fake_storage, label="OrgB")
    return a, b


def _auth(tenant: Tenant) -> dict[str, str]:
    return {"Authorization": f"Bearer {tenant.token}"}


async def _embed_tenant_chunks(client: AsyncClient, tenant: Tenant) -> None:
    """Drive the real embedding endpoint so pgvector rows exist for this
    tenant -- the retrieval tests need real vectors, not fixtures."""

    response = await client.post(
        f"/api/v1/documents/{tenant.document_id}/embeddings", headers=_auth(tenant)
    )
    assert response.status_code == 200, response.text


async def _track_embeddings(ids: Ids, document_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(DocumentChunkEmbeddingModel.id).where(
                DocumentChunkEmbeddingModel.document_id == document_id
            )
        )
        ids.embeddings.extend(result.scalars().all())


# ---------------------------------------------------------------------------
# The fixtures themselves must be real and distinct, or nothing below proves
# anything.
# ---------------------------------------------------------------------------


async def test_the_two_tenants_are_real_distinct_and_both_reachable_by_their_owner(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    """Guards the whole module: if A and B were the same tenant, or if
    either row did not actually exist, every cross-tenant 404 below would
    be vacuous."""

    a, b = tenants
    assert a.organization_id != b.organization_id
    assert a.engagement_id != b.engagement_id
    assert a.document_id != b.document_id

    async with AsyncSessionLocal() as session:
        assert await session.get(DocumentModel, a.document_id) is not None
        assert await session.get(DocumentModel, b.document_id) is not None

    # Same-tenant access works for both, so later denials are about tenancy.
    for tenant in (a, b):
        response = await client.get(
            f"/api/v1/documents/{tenant.document_id}", headers=_auth(tenant)
        )
        assert response.status_code == 200, response.text
        assert response.json()["id"] == str(tenant.document_id)


# ---------------------------------------------------------------------------
# READ / LIST
# ---------------------------------------------------------------------------


async def test_document_read_denies_a_real_foreign_uuid(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    response = await client.get(f"/api/v1/documents/{b.document_id}", headers=_auth(a))

    assert response.status_code == 404
    assert "OrgB" not in response.text
    assert "confidential" not in response.text


async def test_document_list_and_count_never_include_the_other_tenant(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    response = await client.get("/api/v1/documents", headers=_auth(a))

    assert response.status_code == 200
    body = response.json()
    returned = {item["id"] for item in body["items"]}
    assert str(a.document_id) in returned
    assert str(b.document_id) not in returned
    # The pagination total is a separate query; it must be scoped too, or
    # it leaks the existence of the other tenant's rows as a number.
    assert body["total"] == len(returned)


async def test_engagement_read_denies_a_real_foreign_uuid(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    same_tenant = await client.get(f"/api/v1/engagements/{a.engagement_id}", headers=_auth(a))
    cross_tenant = await client.get(f"/api/v1/engagements/{b.engagement_id}", headers=_auth(a))

    assert same_tenant.status_code == 200
    assert cross_tenant.status_code == 404
    assert "OrgB" not in cross_tenant.text


async def test_engagement_list_and_count_never_include_the_other_tenant(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    response = await client.get("/api/v1/engagements", headers=_auth(a))

    assert response.status_code == 200
    body = response.json()
    returned = {item["id"] for item in body["items"]}
    assert str(a.engagement_id) in returned
    assert str(b.engagement_id) not in returned
    assert body["total"] == len(returned)


async def test_organization_read_denies_a_real_foreign_uuid(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    same_tenant = await client.get(
        f"/api/v1/organizations/{a.organization_id}", headers=_auth(a)
    )
    cross_tenant = await client.get(
        f"/api/v1/organizations/{b.organization_id}", headers=_auth(a)
    )

    assert same_tenant.status_code == 200
    assert cross_tenant.status_code == 404
    assert "OrgB" not in cross_tenant.text


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------


async def test_engagement_update_cannot_modify_a_real_foreign_engagement(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    response = await client.patch(
        f"/api/v1/engagements/{b.engagement_id}",
        headers=_auth(a),
        json={"title": "Owned by Organization A now"},
    )

    assert response.status_code == 404
    async with AsyncSessionLocal() as session:
        victim = await session.get(EngagementModel, b.engagement_id)
        assert victim is not None
        assert victim.title == "Slice3 Isolation OrgB Engagement"  # untouched
        assert victim.organization_id == b.organization_id


async def test_organization_update_cannot_rename_the_other_tenant(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    response = await client.patch(
        f"/api/v1/organizations/{b.organization_id}",
        headers=_auth(a),
        json={"name": "Renamed by Organization A"},
    )

    assert response.status_code == 404
    async with AsyncSessionLocal() as session:
        victim = await session.get(OrganizationModel, b.organization_id)
        assert victim is not None
        assert victim.name == "Slice3 Isolation OrgB"  # untouched


# ---------------------------------------------------------------------------
# CREATE ownership -- a client-supplied organization_id is never authority
# ---------------------------------------------------------------------------


async def test_engagement_create_cannot_be_planted_in_the_other_tenant(
    client: AsyncClient, ids: Ids, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    response = await client.post(
        "/api/v1/engagements",
        headers=_auth(a),
        json={
            "organization_id": str(b.organization_id),
            "title": "Planted by Organization A",
            "status": "planning",
        },
    )

    # Rejected outright -- and, crucially, nothing was created anywhere.
    assert response.status_code in (403, 404)
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(EngagementModel).where(
                EngagementModel.title == "Planted by Organization A"
            )
        )
        planted = result.scalars().all()
        ids.engagements.extend(e.id for e in planted)
        assert planted == []


async def test_upload_ownership_comes_from_the_token_not_the_form_field(
    client: AsyncClient, ids: Ids, tenants: tuple[Tenant, Tenant],
    fake_storage: FakeDocumentStorage,
) -> None:
    """User A uploading against Organization B's *real* engagement id must
    fail, and must not write an object into B's storage prefix."""

    a, b = tenants

    response = await client.post(
        "/api/v1/documents",
        headers=_auth(a),
        data={"engagement_id": str(b.engagement_id)},
        files={"file": ("attack.pdf", b"%PDF-1.4 attack", "application/pdf")},
    )

    assert response.status_code == 404
    assert response.status_code != 403, "cross-tenant must not be distinguishable"
    assert fake_storage.put_calls == []

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(DocumentModel).where(DocumentModel.filename == "attack.pdf")
        )
        created = result.scalars().all()
        ids.documents.extend(d.id for d in created)
        assert created == []


async def test_a_legitimate_upload_is_stored_under_the_callers_own_organization(
    client: AsyncClient, ids: Ids, tenants: tuple[Tenant, Tenant],
    fake_storage: FakeDocumentStorage,
) -> None:
    """The positive half: ownership is assigned from trusted context, and
    the storage key encodes the caller's own organization -- never B's."""

    a, b = tenants

    response = await client.post(
        "/api/v1/documents",
        headers=_auth(a),
        data={"engagement_id": str(a.engagement_id)},
        files={"file": ("own-report.pdf", b"%PDF-1.4 legitimate", "application/pdf")},
    )

    assert response.status_code == 201, response.text
    ids.documents.append(uuid.UUID(response.json()["id"]))

    assert len(fake_storage.put_calls) == 1
    key = fake_storage.put_calls[0]
    assert key.startswith(f"organizations/{a.organization_id}/")
    assert str(b.organization_id) not in key


# ---------------------------------------------------------------------------
# PROCESS
# ---------------------------------------------------------------------------


async def test_process_denies_a_real_foreign_document_and_never_claims_it(
    client: AsyncClient, tenants: tuple[Tenant, Tenant], fake_storage: FakeDocumentStorage
) -> None:
    a, b = tenants

    response = await client.post(
        f"/api/v1/documents/{b.document_id}/process", headers=_auth(a)
    )

    assert response.status_code == 404
    # The claim is a conditional UPDATE; if its tenant predicate were
    # missing, B's document would now be PROCESSING (or FAILED).
    assert b.storage_path not in fake_storage.get_calls
    async with AsyncSessionLocal() as session:
        victim = await session.get(DocumentModel, b.document_id)
        assert victim is not None
        assert victim.processing_status == "PROCESSED"  # unchanged


# ---------------------------------------------------------------------------
# EMBEDDING / VECTOR ACCESS
# ---------------------------------------------------------------------------


async def test_embedding_generation_denies_a_real_foreign_document(
    client: AsyncClient, ids: Ids, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    response = await client.post(
        f"/api/v1/documents/{b.document_id}/embeddings", headers=_auth(a)
    )

    assert response.status_code == 404
    await _track_embeddings(ids, b.document_id)
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(DocumentChunkEmbeddingModel).where(
                DocumentChunkEmbeddingModel.document_id == b.document_id
            )
        )
        # No row was claimed against B's chunks, so no provider call was
        # ever made on B's content either.
        assert result.scalars().all() == []


async def test_retrieval_never_returns_the_other_tenants_chunks(
    client: AsyncClient, ids: Ids, tenants: tuple[Tenant, Tenant]
) -> None:
    """Both tenants hold near-identical text, so a shared query is a real
    candidate for both. Only the in-query tenant predicate keeps B's
    vectors out of A's ranking."""

    a, b = tenants
    await _embed_tenant_chunks(client, a)
    await _embed_tenant_chunks(client, b)
    await _track_embeddings(ids, a.document_id)
    await _track_embeddings(ids, b.document_id)

    response = await client.post(
        "/api/v1/retrieval/search",
        headers=_auth(a),
        json={"query": SHARED_TOPIC, "top_k": 50},
    )

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert items, "Organization A must still retrieve its own chunks"
    assert all(item["document_id"] == str(a.document_id) for item in items)
    assert all(str(chunk_id) not in response.text for chunk_id in b.chunk_ids)
    assert "OrgB confidential" not in response.text


async def test_retrieval_document_filter_rejects_a_real_foreign_document(
    client: AsyncClient, ids: Ids, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants
    await _embed_tenant_chunks(client, b)
    await _track_embeddings(ids, b.document_id)

    response = await client.post(
        "/api/v1/retrieval/search",
        headers=_auth(a),
        json={"query": SHARED_TOPIC, "top_k": 10, "document_id": str(b.document_id)},
    )

    assert response.status_code == 404
    assert "confidential" not in response.text


async def test_retrieval_engagement_filter_rejects_a_real_foreign_engagement(
    client: AsyncClient, ids: Ids, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants
    await _embed_tenant_chunks(client, b)
    await _track_embeddings(ids, b.document_id)

    response = await client.post(
        "/api/v1/retrieval/search",
        headers=_auth(a),
        json={"query": SHARED_TOPIC, "top_k": 10, "engagement_id": str(b.engagement_id)},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# ANALYZE
# ---------------------------------------------------------------------------


async def test_analyze_denies_a_real_foreign_document_and_creates_no_run(
    client: AsyncClient, ids: Ids, tenants: tuple[Tenant, Tenant],
    fake_llm_gateway: FakeLLMGateway,
) -> None:
    a, b = tenants

    response = await client.post(
        f"/api/v1/analysis/documents/{b.document_id}/analyze",
        headers=_auth(a),
        json={"analysis_type": "sustainability_summary", "query_text": SHARED_TOPIC},
    )

    assert response.status_code == 404
    assert fake_llm_gateway.call_count == 0, "no model call on another tenant's document"
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(AnalysisRunModel).where(AnalysisRunModel.document_id == b.document_id)
        )
        runs = result.scalars().all()
        ids.runs.extend(r.id for r in runs)
        assert runs == []


async def test_analyze_denies_a_real_foreign_engagement(
    client: AsyncClient, ids: Ids, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    response = await client.post(
        f"/api/v1/analysis/engagements/{b.engagement_id}/analyze",
        headers=_auth(a),
        json={"analysis_type": "sustainability_summary", "query_text": SHARED_TOPIC},
    )

    assert response.status_code == 404


async def test_analysis_run_results_and_citations_are_not_readable_cross_tenant(
    client: AsyncClient, ids: Ids, tenants: tuple[Tenant, Tenant]
) -> None:
    """B runs a real analysis; A then requests it by its real run id. The
    citation rows carry ``quoted_snippet`` -- verbatim text from B's
    document -- so a leak here is direct content disclosure, not metadata."""

    a, b = tenants
    await _embed_tenant_chunks(client, b)
    await _track_embeddings(ids, b.document_id)

    created = await client.post(
        f"/api/v1/analysis/documents/{b.document_id}/analyze",
        headers=_auth(b),
        json={"analysis_type": "sustainability_summary", "query_text": SHARED_TOPIC},
    )
    assert created.status_code == 200, created.text
    run_id = uuid.UUID(created.json()["analysis_run_id"])
    ids.runs.append(run_id)
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(AnalysisSourceReferenceModel.id).where(
                AnalysisSourceReferenceModel.analysis_run_id == run_id
            )
        )
        ids.citations.extend(result.scalars().all())

    owner_view = await client.get(f"/api/v1/analysis/runs/{run_id}", headers=_auth(b))
    attacker_view = await client.get(f"/api/v1/analysis/runs/{run_id}", headers=_auth(a))

    assert owner_view.status_code == 200
    assert attacker_view.status_code == 404
    assert "OrgB confidential" not in attacker_view.text
    assert "12,345" not in attacker_view.text


# ---------------------------------------------------------------------------
# Fail closed: no organization context at all
# ---------------------------------------------------------------------------


async def test_a_user_with_no_organization_is_denied_everywhere(
    client: AsyncClient, ids: Ids, keypair, real_verifier: SupabaseJWTVerifier,
    fake_storage: FakeDocumentStorage, tenants: tuple[Tenant, Tenant],
) -> None:
    """No default organization, no first-organization fallback: a profile
    with ``organization_id IS NULL`` reads nothing and writes nothing."""

    private_key, _public_key = keypair
    a, _b = tenants
    orphan = await _create_tenant(
        ids, private_key, real_verifier, fake_storage,
        label="Orphan", with_organization=False,
    )
    headers = _auth(orphan)

    listing = await client.get("/api/v1/documents", headers=headers)
    detail = await client.get(f"/api/v1/documents/{a.document_id}", headers=headers)
    engagements = await client.get("/api/v1/engagements", headers=headers)
    search = await client.post(
        "/api/v1/retrieval/search", headers=headers, json={"query": SHARED_TOPIC, "top_k": 5}
    )

    assert listing.status_code == 403
    assert detail.status_code == 403
    assert engagements.status_code == 403
    assert search.status_code == 403
    # Above all: never a 200 carrying somebody's rows.
    for response in (listing, detail, engagements, search):
        assert response.status_code != 200


# ---------------------------------------------------------------------------
# A client-supplied organization_id is never the authority
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    ["/api/v1/documents", "/api/v1/engagements"],
)
async def test_a_client_supplied_organization_id_cannot_switch_tenant(
    client: AsyncClient, tenants: tuple[Tenant, Tenant], path: str
) -> None:
    a, b = tenants

    response = await client.get(
        path, headers=_auth(a), params={"organization_id": str(b.organization_id)}
    )

    # Either the parameter is ignored (documents: it is not part of the
    # contract) or it is rejected (engagements: it is, and must match).
    # What must never happen is B's rows coming back.
    assert response.status_code in (200, 403)
    if response.status_code == 200:
        assert str(b.engagement_id) not in response.text
        assert str(b.document_id) not in response.text


async def test_a_forged_organization_header_cannot_switch_tenant(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    """Arbitrary client headers are not a tenant source."""

    a, b = tenants

    response = await client.get(
        "/api/v1/documents",
        headers={
            **_auth(a),
            "X-Organization-Id": str(b.organization_id),
            "X-Tenant-Id": str(b.organization_id),
        },
    )

    assert response.status_code == 200
    assert str(b.document_id) not in response.text


# ---------------------------------------------------------------------------
# Slice 3 closure: the latent unscoped surfaces are gone in behaviour too
#
# The structural half of these -- that the methods do not exist to be
# called -- lives in tests/domain/architecture/test_tenant_scope_guard.py.
# These are the behavioural half, through the real API against real rows.
# ---------------------------------------------------------------------------


async def test_the_organization_endpoint_never_enumerates_other_tenants(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    """``IOrganizationRepository.list``/``count`` used to exist, unused,
    and would have enumerated every tenant on the platform by name. With
    two real organizations present, the listing endpoint must return
    exactly one -- the caller's -- and a total of one."""

    a, b = tenants

    response = await client.get("/api/v1/organizations", headers=_auth(a))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == str(a.organization_id)
    assert str(b.organization_id) not in response.text
    assert "OrgB" not in response.text


async def test_no_route_exposes_a_user_collection(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    """``IUserRepository.list`` used to exist, unused, and returned every
    organization's members with their names and email addresses.

    Two checks, because either alone would be weak: the published schema
    declares no user-collection route, and an *authenticated* caller
    probing the conventional paths gets no user data back. The requests
    are authenticated on purpose -- an unauthenticated 401 would prove
    nothing about what the route does.
    """

    a, b = tenants

    schema = await client.get("/openapi.json")
    assert schema.status_code == 200
    paths = schema.json()["paths"]

    user_collection_paths = [
        path
        for path in paths
        if path.rstrip("/").endswith(("/users", "/members", "/profiles"))
    ]
    assert user_collection_paths == [], user_collection_paths

    # `/api/v1/auth/me` is the only user-shaped route and returns exactly
    # one profile -- the caller's own; it is covered separately below.
    for path in ("/api/v1/users", "/api/v1/organizations/users"):
        response = await client.get(path, headers=_auth(a))
        assert response.status_code != 200, path
        # No other tenant's member data, whatever the status.
        assert str(b.user_id) not in response.text
        assert "OrgB" not in response.text


async def test_the_jwt_subject_bootstrap_still_resolves_the_callers_own_profile(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    """The one documented unscoped read must keep working -- and must
    remain incapable of returning anybody else.

    ``get_by_authenticated_id`` is driven solely by the verified JWT
    ``sub``, so each tenant's token resolves to that tenant's own profile
    and organization, and never to the other's.
    """

    a, b = tenants

    profile_a = await client.get("/api/v1/auth/me", headers=_auth(a))
    profile_b = await client.get("/api/v1/auth/me", headers=_auth(b))

    assert profile_a.status_code == 200, profile_a.text
    assert profile_b.status_code == 200, profile_b.text

    body_a = profile_a.json()
    body_b = profile_b.json()

    assert body_a["id"] == str(a.user_id)
    assert body_a["organization_id"] == str(a.organization_id)
    assert body_b["id"] == str(b.user_id)
    assert body_b["organization_id"] == str(b.organization_id)

    # A's token never yields B's identity, and vice versa.
    assert body_a["id"] != body_b["id"]
    assert str(b.user_id) not in profile_a.text
    assert str(b.organization_id) not in profile_a.text


async def test_an_unprovisioned_subject_is_refused_rather_than_defaulted(
    client: AsyncClient, keypair, real_verifier: SupabaseJWTVerifier
) -> None:
    """Fail closed at the bootstrap itself: a validly-signed token whose
    subject has no profile must be refused, never resolved to some other
    organization's row."""

    private_key, _public_key = keypair
    token = _make_token(
        private_key,
        kid="integration-test-kid",
        overrides={
            "sub": str(uuid.uuid4()),  # no matching public.users row
            "iss": real_verifier.issuer,
            "aud": real_verifier.audience,
        },
    )

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert "organization_id" not in response.text
