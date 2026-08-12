"""Integration API tests for the Document upload endpoint.

Exercises the real orchestration path -- a real ``DocumentUploadService``
wired with real ``IDocumentRepository``/``IEngagementRepository`` against
the configured database -- with only the storage layer swapped for an
in-memory fake. No real Supabase Storage bucket exists yet (confirmed
during Sprint 3.4 planning), so this cannot and does not depend on one;
live-provider storage tests are explicitly out of this sprint's default
coverage.

Authentication uses the same locally-signed-token technique as
``test_auth_integration.py``: the real issuer/audience (from actual
settings) with only the JWKS *fetch* faked -- never touching Supabase's
Auth API, never creating any ``auth.users`` row.

Every row and fake-stored object a test creates is tracked and cleaned up
in dependency-safe order: documents, then engagements, then
users/organizations. No unrelated row or object is ever touched.
"""

import uuid
from typing import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.deps import get_document_storage, get_supabase_jwt_verifier
from app.core.config import get_settings
from app.domain.storage.document_storage import IDocumentStorage
from app.infrastructure.db.models.document import DocumentModel
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

PDF_BYTES = b"%PDF-1.4\n%Integration test PDF content\n%%EOF"


class FakeDocumentStorage(IDocumentStorage):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.delete_calls: list[str] = []

    async def put(self, object_key: str, content: bytes, content_type: str) -> None:
        self.objects[object_key] = content

    async def get(self, object_key: str) -> bytes:
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
    app.dependency_overrides[get_document_storage] = lambda: fake_storage
    yield
    app.dependency_overrides.pop(get_supabase_jwt_verifier, None)
    app.dependency_overrides.pop(get_document_storage, None)


@pytest.fixture
async def cleanup_ids() -> AsyncIterator[dict[str, list[uuid.UUID]]]:
    ids: dict[str, list[uuid.UUID]] = {
        "documents": [],
        "users": [],
        "engagements": [],
        "organizations": [],
    }
    yield ids
    async with AsyncSessionLocal() as cleanup_session:
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


async def _make_organization_engagement_and_profile(
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Creates a real Organization + Engagement + matching ``public.users``
    profile (id standing in for the corresponding ``auth.users`` id, per
    the Sprint 3.3 shared-primary-key identity design). Returns
    ``(organization_id, engagement_id, profile_id)``."""
    async with AsyncSessionLocal() as session:
        organization = OrganizationModel(name="Document Upload Integration Test Org")
        session.add(organization)
        await session.flush()
        cleanup_ids["organizations"].append(organization.id)

        engagement = EngagementModel(
            organization_id=organization.id,
            title="Document Upload Integration Test Engagement",
        )
        session.add(engagement)
        await session.flush()
        cleanup_ids["engagements"].append(engagement.id)

        profile_id = uuid.uuid4()
        profile = UserModel(
            id=profile_id,
            organization_id=organization.id,
            full_name="Document Upload Integration Test User",
            email=f"doc-upload-integration-{profile_id}@example.com",
            role="admin",
        )
        session.add(profile)
        await session.commit()
        cleanup_ids["users"].append(profile_id)

        return organization.id, engagement.id, profile_id


async def test_authenticated_upload_for_matching_organization_persists_document(
    client: AsyncClient,
    keypair,
    real_verifier: SupabaseJWTVerifier,
    fake_storage: FakeDocumentStorage,
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> None:
    private_key, _public_key = keypair
    _organization_id, engagement_id, profile_id = await _make_organization_engagement_and_profile(
        cleanup_ids
    )
    token = _make_token(
        private_key,
        kid="integration-test-kid",
        overrides={
            "sub": str(profile_id),
            "iss": real_verifier.issuer,
            "aud": real_verifier.audience,
        },
    )

    response = await client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"engagement_id": str(engagement_id)},
        files={"file": ("sustainability-report.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()
    cleanup_ids["documents"].append(uuid.UUID(body["id"]))

    assert body["engagement_id"] == str(engagement_id)
    assert body["filename"] == "sustainability-report.pdf"
    assert body["processing_status"] == "PENDING"
    assert "storage_path" not in body

    async with AsyncSessionLocal() as verify_session:
        model = await verify_session.get(DocumentModel, uuid.UUID(body["id"]))
        assert model is not None
        assert model.engagement_id == engagement_id
        assert model.filename == "sustainability-report.pdf"
        assert model.storage_path in fake_storage.objects
        assert fake_storage.objects[model.storage_path] == PDF_BYTES


async def test_upload_for_different_organization_returns_404_and_creates_no_document(
    client: AsyncClient,
    keypair,
    real_verifier: SupabaseJWTVerifier,
    fake_storage: FakeDocumentStorage,
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> None:
    """MVP Slice 3: a real Engagement UUID from another organization is
    rejected as 404, not 403.

    Compare ``test_upload_for_missing_engagement_returns_404`` directly
    below: the two responses are now identical, so a caller cannot use the
    status code to learn that a foreign Engagement UUID is real. Before
    this slice this case returned 403 and that one returned 404.
    """

    private_key, _public_key = keypair
    _organization_id, engagement_id, _profile_id = await _make_organization_engagement_and_profile(
        cleanup_ids
    )

    # A second, unrelated organization + profile -- no relationship to the
    # engagement created above.
    async with AsyncSessionLocal() as session:
        other_organization = OrganizationModel(name="Document Upload Integration Test Other Org")
        session.add(other_organization)
        await session.flush()
        cleanup_ids["organizations"].append(other_organization.id)

        other_profile_id = uuid.uuid4()
        other_profile = UserModel(
            id=other_profile_id,
            organization_id=other_organization.id,
            full_name="Other Org User",
            email=f"other-org-{other_profile_id}@example.com",
            role="admin",
        )
        session.add(other_profile)
        await session.commit()
        cleanup_ids["users"].append(other_profile_id)

    token = _make_token(
        private_key,
        kid="integration-test-kid",
        overrides={
            "sub": str(other_profile_id),
            "iss": real_verifier.issuer,
            "aud": real_verifier.audience,
        },
    )

    response = await client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"engagement_id": str(engagement_id)},
        files={"file": ("sustainability-report.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 404
    assert fake_storage.objects == {}  # nothing was ever stored

    async with AsyncSessionLocal() as verify_session:
        result = await verify_session.execute(
            select(DocumentModel).where(DocumentModel.engagement_id == engagement_id)
        )
        assert result.scalars().all() == []


async def test_upload_for_missing_engagement_returns_404(
    client: AsyncClient,
    keypair,
    real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> None:
    private_key, _public_key = keypair
    _organization_id, _engagement_id, profile_id = await _make_organization_engagement_and_profile(
        cleanup_ids
    )
    token = _make_token(
        private_key,
        kid="integration-test-kid",
        overrides={
            "sub": str(profile_id),
            "iss": real_verifier.issuer,
            "aud": real_verifier.audience,
        },
    )

    response = await client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"engagement_id": str(uuid.uuid4())},
        files={"file": ("sustainability-report.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 404
