"""MVP Slice 4 end to end, against the real database.

Everything here runs through the real ``app``, the real routers, the
real services and the real PostgreSQL + pgvector instance. Only the two
external systems this project never contacts from tests -- the embedding
provider and object storage -- are replaced with in-memory fakes, exactly
as every other integration module in this suite does.

That distinction is the point. ``test_evidence_review_service.py``
proves the lifecycle against a fake repository that *reimplements* the
conditional-write contract; this module proves the contract itself:
that the SQL predicate really is atomic, that PostgreSQL really does
leave the loser of a two-reviewer race with zero updated rows, that the
CHECK constraints really do refuse an inconsistent decision written by
raw SQL, and -- the closure test of this slice -- that the evidence
predicate really is applied before pgvector ranks and truncates, not
after.

**Test identities follow production policy.** No role name is written
into this module: ``_role_with_permissions`` asks the real
``ROLE_PERMISSIONS`` which roles hold the permissions a given journey
needs, and fails with a useful message if none does. The primary tenant
drives both evidence review and embedding generation, so it is derived
from both permissions at once; a change to the policy changes these
identities rather than silently invalidating the tests.

**The two-reviewer tests use two real identities.** Same organization,
different user rows, different signed JWTs, different Authorization
headers. A retry or a race driven by one identity twice would prove
nothing about provenance, which is exactly what those tests exist to
prove.

Every row created is tracked and removed in dependency-safe order in
``ids``'s teardown regardless of outcome.
"""

import hashlib
import uuid
from dataclasses import dataclass
from typing import AsyncIterator, Sequence

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.api.deps import get_document_storage, get_embedding_provider, get_supabase_jwt_verifier
from app.core.config import get_settings
from app.domain.embedding_provider import EmbeddingProvider, EmbeddingResult
from app.domain.evidence.lifecycle import EvidenceStatus
from app.domain.security import Permission, Role, has_permission
from app.domain.storage.document_storage import IDocumentStorage, StorageObjectNotFoundError
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

#: Both retrieval documents talk about this, so either could rank first
#: if the evidence predicate were missing.
SHARED_TOPIC = "scope 1 greenhouse gas emissions intensity"

COMMANDS = ("verify", "reject", "restrict", "supersede")

#: The permissions the primary test identity must hold: it reviews
#: evidence *and* drives ``POST /documents/{id}/embeddings``, which is
#: bound to ``DOCUMENT_PROCESS``.
PRIMARY_JOURNEY_PERMISSIONS = (Permission.EVIDENCE_REVIEW, Permission.DOCUMENT_PROCESS)


def _role_with_permissions(*required_permissions: Permission) -> str:
    """The role production policy says can perform this journey.

    Resolved from ``ROLE_PERMISSIONS`` at call time, never hardcoded: if
    the policy is narrowed (M-4), these tests must follow it or fail
    with a message naming the missing permission -- not keep passing
    under a role name that no longer has the authority."""

    eligible = [
        role.value
        for role in Role
        if all(has_permission(role, permission) for permission in required_permissions)
    ]
    assert eligible, (
        "no role currently holds all of "
        f"{[permission.value for permission in required_permissions]}"
    )
    return eligible[0]


def _deterministic_vector(text_value: str) -> list[float]:
    seed = int(hashlib.sha256(text_value.encode("utf-8")).hexdigest(), 16)
    return [((seed >> (i % 64)) % 1000) / 1000.0 for i in range(DIMENSION)]


def _vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


class FakeEmbeddingProvider(EmbeddingProvider):
    async def embed_texts(self, texts: Sequence[str]) -> Sequence[EmbeddingResult]:
        return [
            EmbeddingResult(text=t, vector=_deterministic_vector(t), dimension=DIMENSION)
            for t in texts
        ]


class FakeDocumentStorage(IDocumentStorage):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.delete_calls: list[str] = []

    def seed(self, object_key: str, content: bytes) -> None:
        self.objects[object_key] = content

    async def put(self, object_key: str, content: bytes, content_type: str) -> None:
        self.objects[object_key] = content

    async def get(self, object_key: str) -> bytes:
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


@pytest.fixture(autouse=True)
def _override_dependencies(
    keypair, real_verifier: SupabaseJWTVerifier, fake_storage: FakeDocumentStorage
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
    app.dependency_overrides[get_document_storage] = lambda: fake_storage
    yield
    for dependency in (get_supabase_jwt_verifier, get_embedding_provider, get_document_storage):
        app.dependency_overrides.pop(dependency, None)


class Ids:
    def __init__(self) -> None:
        self.embeddings: list[uuid.UUID] = []
        self.chunks: list[uuid.UUID] = []
        self.documents: list[uuid.UUID] = []
        self.users: list[uuid.UUID] = []
        self.engagements: list[uuid.UUID] = []
        self.organizations: list[uuid.UUID] = []


@pytest.fixture
async def ids() -> AsyncIterator[Ids]:
    tracked = Ids()
    yield tracked
    async with AsyncSessionLocal() as session:
        # A superseded document references its successor, and a reviewed
        # document references its reviewer, so both pointers are cleared
        # before any row is deleted -- otherwise the self-referencing
        # foreign key and the users foreign key block teardown in
        # whichever order the ids happen to be in.
        if tracked.documents:
            await session.execute(
                text(
                    "UPDATE documents SET superseded_by_document_id = NULL, "
                    "reviewed_by = NULL, reviewed_at = NULL, review_reason = NULL, "
                    "evidence_status = 'PENDING_REVIEW' WHERE id = ANY(:ids)"
                ),
                {"ids": tracked.documents},
            )
            await session.commit()
        for model_cls, id_list in (
            (DocumentChunkEmbeddingModel, tracked.embeddings),
            (DocumentChunkModel, tracked.chunks),
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
class Reviewer:
    """One authenticated human, with their own row and their own token."""

    user_id: uuid.UUID
    role: str
    headers: dict[str, str]


@dataclass
class Tenant:
    organization_id: uuid.UUID
    engagement_id: uuid.UUID
    reviewer: Reviewer

    @property
    def user_id(self) -> uuid.UUID:
        return self.reviewer.user_id

    @property
    def headers(self) -> dict[str, str]:
        return self.reviewer.headers


async def _add_reviewer(
    ids: Ids,
    private_key,
    real_verifier: SupabaseJWTVerifier,
    *,
    organization_id: uuid.UUID,
    label: str,
    permissions: Sequence[Permission],
) -> Reviewer:
    """Create one more authenticated user in an existing organization.

    Each reviewer gets a distinct ``users`` row and a distinct signed
    token, so a test driving two of them is genuinely driving two
    identities through authentication and authorization."""

    role = _role_with_permissions(*permissions)
    user_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        session.add(
            UserModel(
                id=user_id,
                organization_id=organization_id,
                full_name=f"Slice4 {label} Reviewer",
                email=f"slice4-{label.lower()}-{user_id}@example.com",
                role=role,
            )
        )
        await session.commit()
    ids.users.append(user_id)

    token = _make_token(
        private_key,
        kid="integration-test-kid",
        overrides={
            "sub": str(user_id),
            "iss": real_verifier.issuer,
            "aud": real_verifier.audience,
        },
    )
    return Reviewer(user_id=user_id, role=role, headers={"Authorization": f"Bearer {token}"})


async def _create_tenant(
    ids: Ids,
    private_key,
    real_verifier: SupabaseJWTVerifier,
    *,
    label: str,
) -> Tenant:
    async with AsyncSessionLocal() as session:
        organization = OrganizationModel(name=f"Slice4 Evidence {label}")
        session.add(organization)
        await session.flush()
        ids.organizations.append(organization.id)

        engagement = EngagementModel(
            organization_id=organization.id, title=f"Slice4 Evidence {label} Engagement"
        )
        session.add(engagement)
        await session.flush()
        ids.engagements.append(engagement.id)
        await session.commit()

    reviewer = await _add_reviewer(
        ids,
        private_key,
        real_verifier,
        organization_id=organization.id,
        label=label,
        permissions=PRIMARY_JOURNEY_PERMISSIONS,
    )
    return Tenant(
        organization_id=organization.id,
        engagement_id=engagement.id,
        reviewer=reviewer,
    )


async def _create_document(
    ids: Ids,
    tenant: Tenant,
    *,
    processing_status: str = "PROCESSED",
    chunk_contents: Sequence[str] = (),
) -> uuid.UUID:
    """Create a document in the *default* evidence state.

    No test seeds ``evidence_status`` directly: every document starts
    where the column default puts it, and reaches any other state only
    through the real API. That is what keeps these tests honest about
    the lifecycle rather than about the fixture."""

    async with AsyncSessionLocal() as session:
        document = DocumentModel(
            id=uuid.uuid4(),
            filename="report.pdf",
            storage_path=f"slice4/{uuid.uuid4()}.pdf",
            processing_status=processing_status,
            engagement_id=tenant.engagement_id,
        )
        session.add(document)
        await session.flush()
        ids.documents.append(document.id)

        for index, content in enumerate(chunk_contents):
            chunk = DocumentChunkModel(
                document_id=document.id,
                chunk_index=index,
                content=content,
                char_start=0,
                char_end=len(content),
            )
            session.add(chunk)
            await session.flush()
            ids.chunks.append(chunk.id)

        await session.commit()
    return document.id


async def _stored_evidence(document_id: uuid.UUID) -> dict:
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                text(
                    "SELECT evidence_status, processing_status, reviewed_by, reviewed_at, "
                    "review_reason, superseded_by_document_id "
                    "FROM documents WHERE id = :id"
                ),
                {"id": document_id},
            )
        ).mappings().one()
    return dict(row)


def _url(document_id: uuid.UUID, command: str) -> str:
    return f"/api/v1/documents/{document_id}/evidence/{command}"


def _body(command: str, **overrides: object) -> dict:
    body: dict = {} if command == "verify" else {"reason": f"{command} reason"}
    body.update(overrides)
    return body


async def _review(
    client: AsyncClient,
    actor: Tenant | Reviewer,
    document_id: uuid.UUID,
    command: str,
    **overrides: object,
):
    return await client.post(
        _url(document_id, command), headers=actor.headers, json=_body(command, **overrides)
    )


async def _generate_embeddings(
    client: AsyncClient, ids: Ids, tenant: Tenant, document_id: uuid.UUID
) -> None:
    response = await client.post(
        f"/api/v1/documents/{document_id}/embeddings", headers=tenant.headers
    )
    assert response.status_code == 200, response.text
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text("SELECT id FROM document_chunk_embeddings WHERE document_id = :id"),
                {"id": document_id},
            )
        ).scalars().all()
    ids.embeddings.extend(rows)


async def _search(client: AsyncClient, tenant: Tenant, query: str, *, top_k: int = 10) -> list[dict]:
    response = await client.post(
        "/api/v1/retrieval/search", headers=tenant.headers, json={"query": query, "top_k": top_k}
    )
    assert response.status_code == 200, response.text
    return response.json()["items"]


@pytest.fixture
async def tenant(ids: Ids, keypair, real_verifier: SupabaseJWTVerifier) -> Tenant:
    private_key, _public = keypair
    return await _create_tenant(ids, private_key, real_verifier, label="Primary")


@pytest.fixture
async def other_tenant(ids: Ids, keypair, real_verifier: SupabaseJWTVerifier) -> Tenant:
    private_key, _public = keypair
    return await _create_tenant(ids, private_key, real_verifier, label="Foreign")


@pytest.fixture
async def second_reviewer(
    ids: Ids, keypair, real_verifier: SupabaseJWTVerifier, tenant: Tenant
) -> Reviewer:
    """A different human in the *same* organization as ``tenant``."""

    private_key, _public = keypair
    return await _add_reviewer(
        ids,
        private_key,
        real_verifier,
        organization_id=tenant.organization_id,
        label="Second",
        permissions=(Permission.EVIDENCE_REVIEW,),
    )


# ---------------------------------------------------------------------------
# The test identities really are distinct and really are authorized
# ---------------------------------------------------------------------------


async def test_the_derived_test_identities_hold_the_required_permissions(
    tenant: Tenant, second_reviewer: Reviewer
) -> None:
    """Pins what the two-identity tests below depend on, and documents
    the actual roles the live policy selected."""

    primary_role = Role(tenant.reviewer.role)
    secondary_role = Role(second_reviewer.role)

    for permission in PRIMARY_JOURNEY_PERMISSIONS:
        assert has_permission(primary_role, permission)
    assert has_permission(secondary_role, Permission.EVIDENCE_REVIEW)
    assert tenant.user_id != second_reviewer.user_id
    assert tenant.headers != second_reviewer.headers


# ---------------------------------------------------------------------------
# The initial state
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("processing_status", ["PENDING", "PROCESSING", "PROCESSED", "FAILED"])
async def test_a_new_document_lands_in_pending_review(
    ids: Ids, tenant: Tenant, processing_status: str
) -> None:
    """The column default, observed through the database itself: no code
    path had to remember to set it, whatever the processing state."""

    document_id = await _create_document(ids, tenant, processing_status=processing_status)

    stored = await _stored_evidence(document_id)

    assert stored["evidence_status"] == EvidenceStatus.PENDING_REVIEW.value
    assert stored["reviewed_by"] is None
    assert stored["reviewed_at"] is None
    assert stored["review_reason"] is None


async def test_a_processed_document_without_an_explicit_evidence_decision_defaults_fail_closed(
    client: AsyncClient, ids: Ids, tenant: Tenant
) -> None:
    """A row inserted by raw SQL that never names ``evidence_status`` --
    the shape every pre-Slice-4 insert had -- is PENDING_REVIEW and
    contributes nothing to retrieval until a human approves it.

    This proves the *column default* is fail-closed, not the Alembic
    migration of rows that existed beforehand: this row is created after
    the migration has already run. The genuine pre-migration proof, which
    inserts against revision ``a4f1c9d2e7b3`` and then upgrades, lives in
    ``tests/integration/test_evidence_migration.py``."""

    async with AsyncSessionLocal() as session:
        document_id = uuid.uuid4()
        await session.execute(
            text(
                "INSERT INTO documents (id, filename, storage_path, processing_status, "
                "engagement_id) VALUES (:id, :filename, :path, 'PROCESSED', :engagement_id)"
            ),
            {
                "id": document_id,
                "filename": "no-evidence-column.pdf",
                "path": f"slice4-default/{uuid.uuid4()}.pdf",
                "engagement_id": tenant.engagement_id,
            },
        )
        chunk_id = uuid.uuid4()
        content = f"Unapproved disclosure: {SHARED_TOPIC} was 900 tCO2e."
        await session.execute(
            text(
                "INSERT INTO document_chunks (id, document_id, chunk_index, content, "
                "char_start, char_end) VALUES (:id, :document_id, 0, :content, 0, :end)"
            ),
            {
                "id": chunk_id,
                "document_id": document_id,
                "content": content,
                "end": len(content),
            },
        )
        await session.commit()
    ids.documents.append(document_id)
    ids.chunks.append(chunk_id)

    stored = await _stored_evidence(document_id)
    assert stored["evidence_status"] == EvidenceStatus.PENDING_REVIEW.value

    await _generate_embeddings(client, ids, tenant, document_id)
    items = await _search(client, tenant, content)

    assert [item for item in items if item["document_id"] == str(document_id)] == []


# ---------------------------------------------------------------------------
# The transition matrix, against the real database
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("verify", EvidenceStatus.VERIFIED),
        ("reject", EvidenceStatus.REJECTED),
        ("restrict", EvidenceStatus.RESTRICTED),
        ("supersede", EvidenceStatus.SUPERSEDED),
    ],
)
async def test_every_command_is_allowed_from_pending_review(
    client: AsyncClient, ids: Ids, tenant: Tenant, command: str, expected: EvidenceStatus
) -> None:
    document_id = await _create_document(ids, tenant)

    response = await _review(client, tenant, document_id, command)

    assert response.status_code == 200, response.text
    assert response.json()["evidence_status"] == expected.value
    stored = await _stored_evidence(document_id)
    assert stored["evidence_status"] == expected.value
    # Provenance is server-derived and actually persisted.
    assert stored["reviewed_by"] == tenant.user_id
    assert stored["reviewed_at"] is not None


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("reject", EvidenceStatus.REJECTED),
        ("restrict", EvidenceStatus.RESTRICTED),
        ("supersede", EvidenceStatus.SUPERSEDED),
    ],
)
async def test_verified_evidence_can_be_withdrawn(
    client: AsyncClient, ids: Ids, tenant: Tenant, command: str, expected: EvidenceStatus
) -> None:
    document_id = await _create_document(ids, tenant)
    assert (await _review(client, tenant, document_id, "verify")).status_code == 200

    response = await _review(client, tenant, document_id, command)

    assert response.status_code == 200, response.text
    assert (await _stored_evidence(document_id))["evidence_status"] == expected.value


@pytest.mark.parametrize("decided", ["reject", "restrict", "supersede"])
async def test_a_decided_document_cannot_be_reactivated(
    client: AsyncClient, ids: Ids, tenant: Tenant, decided: str
) -> None:
    """The invariant this slice exists to protect: no client-reachable
    request returns a withdrawn document to the retrievable state."""

    document_id = await _create_document(ids, tenant)
    assert (await _review(client, tenant, document_id, decided)).status_code == 200
    before = await _stored_evidence(document_id)

    response = await _review(client, tenant, document_id, "verify")

    assert response.status_code == 409
    assert await _stored_evidence(document_id) == before


@pytest.mark.parametrize("decided", ["reject", "restrict", "supersede"])
@pytest.mark.parametrize("attempted", ["reject", "restrict", "supersede"])
async def test_terminal_states_refuse_every_other_decision(
    client: AsyncClient, ids: Ids, tenant: Tenant, decided: str, attempted: str
) -> None:
    """Both the cross-decision case (REJECTED -> RESTRICTED) and the
    same-command-different-reason case are refused, and neither writes."""

    document_id = await _create_document(ids, tenant)
    assert (await _review(client, tenant, document_id, decided)).status_code == 200
    before = await _stored_evidence(document_id)

    response = await _review(client, tenant, document_id, attempted, reason="a different reason")

    assert response.status_code == 409
    assert await _stored_evidence(document_id) == before


# ---------------------------------------------------------------------------
# The processing precondition, against the real database
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("processing_status", ["PENDING", "PROCESSING", "FAILED"])
async def test_verify_is_refused_unless_the_document_is_processed(
    client: AsyncClient, ids: Ids, tenant: Tenant, processing_status: str
) -> None:
    document_id = await _create_document(ids, tenant, processing_status=processing_status)

    response = await _review(client, tenant, document_id, "verify")

    assert response.status_code == 409
    assert processing_status in response.json()["detail"]
    assert (await _stored_evidence(document_id))[
        "evidence_status"
    ] == EvidenceStatus.PENDING_REVIEW.value


async def test_verify_succeeds_on_a_processed_document(
    client: AsyncClient, ids: Ids, tenant: Tenant
) -> None:
    document_id = await _create_document(ids, tenant, processing_status="PROCESSED")

    response = await _review(client, tenant, document_id, "verify")

    assert response.status_code == 200
    assert (await _stored_evidence(document_id))["evidence_status"] == EvidenceStatus.VERIFIED.value


@pytest.mark.parametrize("command", ["reject", "restrict", "supersede"])
@pytest.mark.parametrize("processing_status", ["PENDING", "PROCESSING", "FAILED"])
async def test_withdrawal_works_in_every_processing_state(
    client: AsyncClient, ids: Ids, tenant: Tenant, command: str, processing_status: str
) -> None:
    """A document whose extraction failed must still be refusable."""

    document_id = await _create_document(ids, tenant, processing_status=processing_status)

    response = await _review(client, tenant, document_id, command)

    assert response.status_code == 200, response.text


async def test_a_processing_change_between_read_and_write_blocks_verification(
    client: AsyncClient, ids: Ids, tenant: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The precondition is in the UPDATE's predicate, not only in the
    earlier check. The document is PROCESSED when the service reads it
    and PROCESSING by the time the conditional write runs -- against the
    real database, the statement matches zero rows and the approval does
    not happen. The monkeypatch only opens the window; the write itself
    is the real repository statement against real PostgreSQL."""

    document_id = await _create_document(ids, tenant, processing_status="PROCESSED")

    from app.infrastructure.repositories.document import SQLAlchemyDocumentRepository

    original = SQLAlchemyDocumentRepository.transition_evidence

    async def reprocess_then_transition(self, document_id_arg, **kwargs):
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE documents SET processing_status = 'PROCESSING' WHERE id = :id"),
                {"id": document_id_arg},
            )
            await session.commit()
        return await original(self, document_id_arg, **kwargs)

    monkeypatch.setattr(
        SQLAlchemyDocumentRepository, "transition_evidence", reprocess_then_transition
    )

    response = await _review(client, tenant, document_id, "verify")

    assert response.status_code == 409
    stored = await _stored_evidence(document_id)
    assert stored["evidence_status"] == EvidenceStatus.PENDING_REVIEW.value
    assert stored["processing_status"] == "PROCESSING"


# ---------------------------------------------------------------------------
# Concurrency and retry, with two real reviewers
# ---------------------------------------------------------------------------


async def test_a_stale_reviewer_cannot_overwrite_a_newer_decision(
    client: AsyncClient,
    ids: Ids,
    tenant: Tenant,
    second_reviewer: Reviewer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two different authenticated humans, one document.

    Reviewer B (the primary tenant identity) observes PENDING_REVIEW and
    begins a VERIFY. Before B's conditional UPDATE runs, Reviewer A -- a
    genuinely separate user row with a separate JWT -- records a REJECT
    through the real HTTP API. A wins. B's stale write carries the state
    B observed, so PostgreSQL matches zero rows, and A's decision,
    reviewer identity and reason all survive intact.

    The monkeypatch exists only to make the interleaving deterministic;
    both decisions travel the real router, authorization, service,
    repository and database."""

    reviewer_a = second_reviewer
    reviewer_b = tenant.reviewer
    assert reviewer_a.user_id != reviewer_b.user_id

    document_id = await _create_document(ids, tenant)

    from app.infrastructure.repositories.document import SQLAlchemyDocumentRepository

    original = SQLAlchemyDocumentRepository.transition_evidence
    interleaved: list[str] = []

    async def reviewer_a_decides_first(self, document_id_arg, **kwargs):
        if not interleaved:
            interleaved.append("A")
            reject = await client.post(
                _url(document_id_arg, "reject"),
                headers=reviewer_a.headers,
                json={"reason": "reviewer A: unverifiable emissions factor"},
            )
            assert reject.status_code == 200, reject.text
        return await original(self, document_id_arg, **kwargs)

    monkeypatch.setattr(
        SQLAlchemyDocumentRepository, "transition_evidence", reviewer_a_decides_first
    )

    response = await client.post(
        _url(document_id, "verify"), headers=reviewer_b.headers, json={}
    )

    assert response.status_code == 409
    assert "REJECTED" in response.json()["detail"]
    stored = await _stored_evidence(document_id)
    assert stored["evidence_status"] == EvidenceStatus.REJECTED.value
    assert stored["reviewed_by"] == reviewer_a.user_id
    assert stored["reviewed_by"] != reviewer_b.user_id
    assert stored["review_reason"] == "reviewer A: unverifiable emissions factor"


async def test_a_duplicate_command_preserves_the_first_reviewers_provenance(
    client: AsyncClient, ids: Ids, tenant: Tenant, second_reviewer: Reviewer
) -> None:
    """Reviewer A verifies; Reviewer B -- a different authenticated user
    in the same organization -- issues the materially identical VERIFY.

    B's request succeeds idempotently and returns the decision that
    already stands. It does not rewrite the record in B's name: the
    stored reviewer, timestamp and reason are still A's."""

    reviewer_a = tenant.reviewer
    reviewer_b = second_reviewer
    assert reviewer_a.user_id != reviewer_b.user_id

    document_id = await _create_document(ids, tenant)

    first = await _review(client, reviewer_a, document_id, "verify", reason="checked totals")
    assert first.status_code == 200, first.text
    stored_after_first = await _stored_evidence(document_id)

    second = await _review(client, reviewer_b, document_id, "verify", reason="checked totals")

    assert second.status_code == 200, second.text
    assert second.json() == first.json()

    stored_after_second = await _stored_evidence(document_id)
    assert stored_after_second == stored_after_first
    assert stored_after_second["reviewed_by"] == reviewer_a.user_id
    assert stored_after_second["reviewed_by"] != reviewer_b.user_id
    assert stored_after_second["reviewed_at"] == stored_after_first["reviewed_at"]
    assert stored_after_second["review_reason"] == "checked totals"


async def test_a_repeat_with_a_different_reason_is_refused(
    client: AsyncClient, ids: Ids, tenant: Tenant, second_reviewer: Reviewer
) -> None:
    """A second reviewer's differing justification must not silently
    replace the recorded one."""

    document_id = await _create_document(ids, tenant)
    assert (
        await _review(client, tenant, document_id, "reject", reason="wrong period")
    ).status_code == 200
    before = await _stored_evidence(document_id)

    response = await _review(
        client, second_reviewer, document_id, "reject", reason="unverifiable factor"
    )

    assert response.status_code == 409
    assert await _stored_evidence(document_id) == before


async def test_a_repeated_supersede_with_a_different_successor_is_refused(
    client: AsyncClient, ids: Ids, tenant: Tenant
) -> None:
    document_id = await _create_document(ids, tenant)
    first_successor = await _create_document(ids, tenant)
    second_successor = await _create_document(ids, tenant)

    assert (
        await _review(
            client,
            tenant,
            document_id,
            "supersede",
            reason="replaced",
            superseded_by_document_id=str(first_successor),
        )
    ).status_code == 200
    before = await _stored_evidence(document_id)

    response = await _review(
        client,
        tenant,
        document_id,
        "supersede",
        reason="replaced",
        superseded_by_document_id=str(second_successor),
    )

    assert response.status_code == 409
    stored = await _stored_evidence(document_id)
    assert stored == before
    assert stored["superseded_by_document_id"] == first_successor


# ---------------------------------------------------------------------------
# Tenant isolation and successor rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", COMMANDS)
async def test_another_organizations_document_cannot_be_reviewed(
    client: AsyncClient, ids: Ids, tenant: Tenant, other_tenant: Tenant, command: str
) -> None:
    """A real, valid foreign UUID -- read straight out of the database --
    behaves exactly like an unknown one, and nothing is written."""

    foreign_document = await _create_document(ids, other_tenant)
    before = await _stored_evidence(foreign_document)

    response = await _review(client, tenant, foreign_document, command)

    assert response.status_code == 404
    assert await _stored_evidence(foreign_document) == before


@pytest.mark.parametrize("command", COMMANDS)
async def test_an_unknown_document_is_the_same_404(
    client: AsyncClient, tenant: Tenant, command: str
) -> None:
    response = await _review(client, tenant, uuid.uuid4(), command)

    assert response.status_code == 404


async def test_a_document_cannot_supersede_itself(
    client: AsyncClient, ids: Ids, tenant: Tenant
) -> None:
    document_id = await _create_document(ids, tenant)

    response = await _review(
        client,
        tenant,
        document_id,
        "supersede",
        reason="replaced",
        superseded_by_document_id=str(document_id),
    )

    assert response.status_code == 422
    assert (await _stored_evidence(document_id))[
        "evidence_status"
    ] == EvidenceStatus.PENDING_REVIEW.value


async def test_an_unknown_successor_is_not_found(
    client: AsyncClient, ids: Ids, tenant: Tenant
) -> None:
    document_id = await _create_document(ids, tenant)

    response = await _review(
        client,
        tenant,
        document_id,
        "supersede",
        reason="replaced",
        superseded_by_document_id=str(uuid.uuid4()),
    )

    assert response.status_code == 404
    assert (await _stored_evidence(document_id))[
        "evidence_status"
    ] == EvidenceStatus.PENDING_REVIEW.value


async def test_a_cross_tenant_successor_is_the_same_404(
    client: AsyncClient, ids: Ids, tenant: Tenant, other_tenant: Tenant
) -> None:
    """A valid UUID belonging to another organization must not become an
    existence oracle: same status, and the supersession does not happen."""

    document_id = await _create_document(ids, tenant)
    foreign_successor = await _create_document(ids, other_tenant)

    response = await _review(
        client,
        tenant,
        document_id,
        "supersede",
        reason="replaced",
        superseded_by_document_id=str(foreign_successor),
    )

    assert response.status_code == 404
    assert (await _stored_evidence(document_id))[
        "evidence_status"
    ] == EvidenceStatus.PENDING_REVIEW.value


async def test_a_same_tenant_successor_is_recorded_but_never_verified(
    client: AsyncClient, ids: Ids, tenant: Tenant
) -> None:
    """The V4 -> V5 scenario: marking V4 SUPERSEDED must not approve V5.
    V5 stays PENDING_REVIEW until a human verifies it in its own right,
    and only then becomes retrievable."""

    v4 = await _create_document(ids, tenant)
    v5 = await _create_document(ids, tenant)

    response = await _review(
        client,
        tenant,
        v4,
        "supersede",
        reason="replaced by the FY25 restatement",
        superseded_by_document_id=str(v5),
    )

    assert response.status_code == 200
    stored_v4 = await _stored_evidence(v4)
    assert stored_v4["evidence_status"] == EvidenceStatus.SUPERSEDED.value
    assert stored_v4["superseded_by_document_id"] == v5

    successor = await _stored_evidence(v5)
    assert successor["evidence_status"] == EvidenceStatus.PENDING_REVIEW.value
    assert successor["reviewed_by"] is None
    assert successor["reviewed_at"] is None

    assert (await _review(client, tenant, v5, "verify")).status_code == 200
    assert (await _stored_evidence(v5))["evidence_status"] == EvidenceStatus.VERIFIED.value


# ---------------------------------------------------------------------------
# Verified-only retrieval
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("command", "state"),
    [
        (None, EvidenceStatus.PENDING_REVIEW),
        ("reject", EvidenceStatus.REJECTED),
        ("restrict", EvidenceStatus.RESTRICTED),
        ("supersede", EvidenceStatus.SUPERSEDED),
    ],
)
async def test_only_verified_documents_are_retrievable(
    client: AsyncClient,
    ids: Ids,
    tenant: Tenant,
    command: str | None,
    state: EvidenceStatus,
) -> None:
    content = f"Ineligible disclosure: {SHARED_TOPIC} was 4,200 tCO2e."
    document_id = await _create_document(ids, tenant, chunk_contents=[content])
    await _generate_embeddings(client, ids, tenant, document_id)

    if command is not None:
        assert (await _review(client, tenant, document_id, command)).status_code == 200
    assert (await _stored_evidence(document_id))["evidence_status"] == state.value

    items = await _search(client, tenant, content)

    assert [item for item in items if item["document_id"] == str(document_id)] == []


async def test_a_verified_document_is_retrievable(
    client: AsyncClient, ids: Ids, tenant: Tenant
) -> None:
    content = f"Approved disclosure: {SHARED_TOPIC} was 4,200 tCO2e."
    document_id = await _create_document(ids, tenant, chunk_contents=[content])
    await _generate_embeddings(client, ids, tenant, document_id)

    assert (await _review(client, tenant, document_id, "verify")).status_code == 200
    items = await _search(client, tenant, content)

    assert [item["document_id"] for item in items] == [str(document_id)]


@pytest.mark.parametrize("withdrawal", ["reject", "restrict", "supersede"])
async def test_withdrawal_excludes_the_document_from_the_next_retrieval(
    client: AsyncClient, ids: Ids, tenant: Tenant, withdrawal: str
) -> None:
    """Exclusion is immediate and needs no re-embedding: the state is
    read live from ``documents`` by the same query that ranks."""

    content = f"Withdrawn disclosure: {SHARED_TOPIC} was 7,700 tCO2e."
    document_id = await _create_document(ids, tenant, chunk_contents=[content])
    await _generate_embeddings(client, ids, tenant, document_id)
    assert (await _review(client, tenant, document_id, "verify")).status_code == 200

    assert [item["document_id"] for item in await _search(client, tenant, content)] == [
        str(document_id)
    ]

    assert (await _review(client, tenant, document_id, withdrawal)).status_code == 200

    assert await _search(client, tenant, content) == []

    # The embeddings are still there -- withdrawal changes eligibility,
    # not the work already done.
    async with AsyncSessionLocal() as session:
        remaining = (
            await session.execute(
                text(
                    "SELECT count(*) FROM document_chunk_embeddings "
                    "WHERE document_id = :id AND status = 'COMPLETED'"
                ),
                {"id": document_id},
            )
        ).scalar_one()
    assert remaining == 1


@pytest.mark.parametrize("command", COMMANDS)
async def test_no_evidence_command_deletes_chunks_or_embeddings(
    client: AsyncClient,
    ids: Ids,
    tenant: Tenant,
    fake_storage: FakeDocumentStorage,
    command: str,
) -> None:
    """No evidence decision -- approval or withdrawal -- destroys work.

    Rejection in particular must not delete the record of what was
    rejected, and eligibility must be enforced by the retrieval
    predicate rather than by deleting vectors."""

    content = f"Retained disclosure: {SHARED_TOPIC} was 1,100 tCO2e."
    document_id = await _create_document(ids, tenant, chunk_contents=[content])
    await _generate_embeddings(client, ids, tenant, document_id)

    assert (await _review(client, tenant, document_id, command)).status_code == 200

    async with AsyncSessionLocal() as session:
        documents = (
            await session.execute(
                text("SELECT count(*) FROM documents WHERE id = :id"), {"id": document_id}
            )
        ).scalar_one()
        chunks = (
            await session.execute(
                text("SELECT count(*) FROM document_chunks WHERE document_id = :id"),
                {"id": document_id},
            )
        ).scalar_one()
        embeddings = (
            await session.execute(
                text(
                    "SELECT count(*) FROM document_chunk_embeddings "
                    "WHERE document_id = :id AND status = 'COMPLETED'"
                ),
                {"id": document_id},
            )
        ).scalar_one()

    assert (documents, chunks, embeddings) == (1, 1, 1)
    assert fake_storage.delete_calls == []


async def test_embeddings_may_be_generated_before_verification(
    client: AsyncClient, ids: Ids, tenant: Tenant
) -> None:
    """Verification gates retrieval eligibility, not whether embedding
    work may happen -- the pipeline stays independent of the review."""

    content = f"Unreviewed disclosure: {SHARED_TOPIC} was 3,300 tCO2e."
    document_id = await _create_document(ids, tenant, chunk_contents=[content])

    await _generate_embeddings(client, ids, tenant, document_id)

    stored = await _stored_evidence(document_id)
    assert stored["evidence_status"] == EvidenceStatus.PENDING_REVIEW.value
    async with AsyncSessionLocal() as session:
        completed = (
            await session.execute(
                text(
                    "SELECT count(*) FROM document_chunk_embeddings "
                    "WHERE document_id = :id AND status = 'COMPLETED'"
                ),
                {"id": document_id},
            )
        ).scalar_one()
    assert completed == 1


# ---------------------------------------------------------------------------
# THE CLOSURE TEST: the predicate runs before ranking, not after
# ---------------------------------------------------------------------------


async def test_a_stronger_unverified_match_never_displaces_a_verified_one(
    client: AsyncClient, ids: Ids, tenant: Tenant
) -> None:
    """The Slice 4 closure test.

    Document A is REJECTED and holds the *exact* query text, so its
    cosine distance is 0 -- the strongest match physically possible.
    Document B is VERIFIED and holds merely related text. The search
    asks for ``top_k=1``.

    * A correct implementation puts ``evidence_status`` in the same
      WHERE clause as the ORDER BY, so A is never a candidate and B is
      returned.
    * An implementation that ranks first and filters afterwards ranks A
      into the single available slot, filters it out, and returns an
      empty list.

    So the assertion below distinguishes the two designs -- it is not
    merely asserting that a rejected document is absent, which a
    post-filter would also satisfy."""

    exact_query = f"Exact match text about {SHARED_TOPIC} for the ranking test."
    weaker = f"Related commentary on {SHARED_TOPIC} with different wording entirely."

    rejected_document = await _create_document(ids, tenant, chunk_contents=[exact_query])
    verified_document = await _create_document(ids, tenant, chunk_contents=[weaker])
    await _generate_embeddings(client, ids, tenant, rejected_document)
    await _generate_embeddings(client, ids, tenant, verified_document)

    assert (await _review(client, tenant, rejected_document, "reject")).status_code == 200
    assert (await _review(client, tenant, verified_document, "verify")).status_code == 200

    # Sanity, and the part that makes the real assertion below meaningful:
    # with no evidence predicate at all, the rejected document wins this
    # query outright. Proved directly against pgvector, returning *both*
    # distances rather than relying on LIMIT 1 -- so a fixture that drifted
    # into a tie, or a query text that stopped matching exactly, fails here
    # with the actual numbers instead of silently making the closure
    # assertion vacuous.
    #
    # `:query` is bound as a bare vector literal, the same convention
    # `SQLAlchemyDocumentChunkEmbeddingRepository.search` uses. Verified
    # against this project's PostgreSQL 16 + pgvector 0.8.6 that it
    # resolves identically to `CAST(:query AS vector)`: same winner, same
    # ordering, same distances.
    async with AsyncSessionLocal() as session:
        ranked = (
            await session.execute(
                text(
                    "SELECT document_id, embedding <=> :query AS distance "
                    "FROM document_chunk_embeddings "
                    "WHERE organization_id = :org AND status = 'COMPLETED' "
                    "ORDER BY distance"
                ),
                {
                    "org": tenant.organization_id,
                    "query": _vector_literal(_deterministic_vector(exact_query)),
                },
            )
        ).mappings().all()

    distances = {row["document_id"]: float(row["distance"]) for row in ranked}
    assert set(distances) == {rejected_document, verified_document}
    assert distances[rejected_document] == pytest.approx(0.0, abs=1e-9), (
        "the rejected document no longer holds the exact query text"
    )
    assert distances[rejected_document] < distances[verified_document], (
        "fixture no longer makes the rejected document the stronger match: "
        f"rejected={distances[rejected_document]} verified={distances[verified_document]}"
    )
    assert ranked[0]["document_id"] == rejected_document

    items = await _search(client, tenant, exact_query, top_k=1)

    assert [item["document_id"] for item in items] == [str(verified_document)], (
        "a post-ranking filter would return an empty list here; the evidence "
        "predicate must be applied before ORDER BY and LIMIT"
    )


# ---------------------------------------------------------------------------
# Database-level constraints
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "invalid_state",
    [
        # A decided state with no reviewer or timestamp.
        "evidence_status = 'VERIFIED'",
        # A rejection with no reason.
        "evidence_status = 'REJECTED', reviewed_by = :user, reviewed_at = now()",
        # A restriction with no reason.
        "evidence_status = 'RESTRICTED', reviewed_by = :user, reviewed_at = now()",
        # A supersession with no reason.
        "evidence_status = 'SUPERSEDED', reviewed_by = :user, reviewed_at = now()",
        # An unapproved state carrying review metadata anyway.
        "evidence_status = 'PENDING_REVIEW', reviewed_by = :user, reviewed_at = now()",
        # A state outside the catalogue.
        "evidence_status = 'APPROVED'",
        # A blank reason.
        (
            "evidence_status = 'REJECTED', reviewed_by = :user, reviewed_at = now(), "
            "review_reason = '   '"
        ),
    ],
)
async def test_the_database_refuses_an_inconsistent_evidence_row(
    ids: Ids, tenant: Tenant, invalid_state: str
) -> None:
    """The CHECK constraints are the backstop for any writer that
    bypasses the service layer entirely -- a migration, a console, or a
    future bug."""

    document_id = await _create_document(ids, tenant)

    async with AsyncSessionLocal() as session:
        with pytest.raises(Exception) as excinfo:
            await session.execute(
                text(f"UPDATE documents SET {invalid_state} WHERE id = :id"),
                {"id": document_id, "user": tenant.user_id},
            )
            await session.commit()
        assert "violates check constraint" in str(excinfo.value).lower()
        await session.rollback()

    assert (await _stored_evidence(document_id))[
        "evidence_status"
    ] == EvidenceStatus.PENDING_REVIEW.value


async def test_the_database_refuses_a_self_supersession(ids: Ids, tenant: Tenant) -> None:
    document_id = await _create_document(ids, tenant)

    async with AsyncSessionLocal() as session:
        with pytest.raises(Exception) as excinfo:
            await session.execute(
                text(
                    "UPDATE documents SET evidence_status = 'SUPERSEDED', reviewed_by = :user, "
                    "reviewed_at = now(), review_reason = 'self', "
                    "superseded_by_document_id = :id WHERE id = :id"
                ),
                {"id": document_id, "user": tenant.user_id},
            )
            await session.commit()
        assert "ck_documents_not_superseded_by_self" in str(excinfo.value)
        await session.rollback()


async def test_the_database_refuses_an_over_long_reason(ids: Ids, tenant: Tenant) -> None:
    document_id = await _create_document(ids, tenant)

    async with AsyncSessionLocal() as session:
        with pytest.raises(Exception) as excinfo:
            await session.execute(
                text(
                    "UPDATE documents SET evidence_status = 'REJECTED', reviewed_by = :user, "
                    "reviewed_at = now(), review_reason = :reason WHERE id = :id"
                ),
                {"id": document_id, "user": tenant.user_id, "reason": "x" * 1001},
            )
            await session.commit()
        assert "ck_documents_review_reason_format" in str(excinfo.value)
        await session.rollback()


# ---------------------------------------------------------------------------
# The read model exposes the decision
# ---------------------------------------------------------------------------


async def test_the_document_read_api_reports_the_current_decision(
    client: AsyncClient, ids: Ids, tenant: Tenant
) -> None:
    document_id = await _create_document(ids, tenant)
    assert (
        await _review(client, tenant, document_id, "restrict", reason="client confidential")
    ).status_code == 200

    response = await client.get(f"/api/v1/documents/{document_id}", headers=tenant.headers)

    assert response.status_code == 200
    body = response.json()
    assert body["evidence_status"] == EvidenceStatus.RESTRICTED.value
    assert body["reviewed_by"] == str(tenant.user_id)
    assert body["review_reason"] == "client confidential"
    assert body["processing_status"] == "PROCESSED"


async def test_the_document_list_can_filter_a_review_queue(
    client: AsyncClient, ids: Ids, tenant: Tenant
) -> None:
    pending = await _create_document(ids, tenant)
    verified = await _create_document(ids, tenant)
    assert (await _review(client, tenant, verified, "verify")).status_code == 200

    response = await client.get(
        "/api/v1/documents",
        headers=tenant.headers,
        params={"evidence_status": "PENDING_REVIEW", "engagement_id": str(tenant.engagement_id)},
    )

    assert response.status_code == 200
    body = response.json()
    returned = {item["id"] for item in body["items"]}
    assert str(pending) in returned
    assert str(verified) not in returned
    # The count reflects the same filter as the page, not the tenant total.
    assert body["total"] == len(body["items"])


async def test_an_unknown_evidence_status_filter_is_422(
    client: AsyncClient, tenant: Tenant
) -> None:
    response = await client.get(
        "/api/v1/documents", headers=tenant.headers, params={"evidence_status": "APPROVED"}
    )

    assert response.status_code == 422
