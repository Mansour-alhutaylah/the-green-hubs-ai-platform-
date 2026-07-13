"""Focused end-to-end integration tests for the Document processing
endpoint (``POST /api/v1/documents/{document_id}/process``).

Exercises the real orchestration path -- a real ``DocumentProcessingService``
wired with real ``IDocumentRepository``/``IEngagementRepository``/
``IExtractedTextRepository``/``IDocumentChunkRepository``/
``IProcessingUnitOfWork`` against the configured database -- with only the
storage layer swapped for an in-memory fake seeded with real, valid PDF
bytes (no live Supabase Storage bucket exists yet, per Sprint 3.4's
precedent in ``test_documents_integration.py``).

Authentication uses the same locally-signed-token technique as
``test_auth_integration.py``/``test_documents_integration.py``: the real
issuer/audience with only the JWKS *fetch* faked.

Every row a test creates is tracked and cleaned up in dependency-safe
order: document_chunks/extracted_text, then documents, then
engagements/users/organizations. No unrelated row is ever touched.
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
from app.infrastructure.db.models.document_chunk import DocumentChunkModel
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


def _make_pdf_bytes(text: str = "Integration test document content") -> bytes:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    rect = pymupdf.Rect(36, 36, page.rect.width - 36, page.rect.height - 36)
    page.insert_textbox(rect, text, fontsize=8)
    content = doc.tobytes()
    doc.close()
    return content


class FakeDocumentStorage(IDocumentStorage):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def seed(self, object_key: str, content: bytes) -> None:
        self.objects[object_key] = content

    async def put(self, object_key: str, content: bytes, content_type: str) -> None:
        self.objects[object_key] = content

    async def get(self, object_key: str) -> bytes:
        return self.objects[object_key]

    async def delete(self, object_key: str) -> None:
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
        "chunks": [],
        "extracted_text": [],
        "documents": [],
        "users": [],
        "engagements": [],
        "organizations": [],
    }
    yield ids
    async with AsyncSessionLocal() as cleanup_session:
        for chunk_id in ids["chunks"]:
            model = await cleanup_session.get(DocumentChunkModel, chunk_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for extracted_text_id in ids["extracted_text"]:
            model = await cleanup_session.get(ExtractedTextModel, extracted_text_id)
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


async def _make_organization_engagement_and_profile(
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    async with AsyncSessionLocal() as session:
        organization = OrganizationModel(name="Document Processing Integration Test Org")
        session.add(organization)
        await session.flush()
        cleanup_ids["organizations"].append(organization.id)

        engagement = EngagementModel(
            organization_id=organization.id,
            title="Document Processing Integration Test Engagement",
        )
        session.add(engagement)
        await session.flush()
        cleanup_ids["engagements"].append(engagement.id)

        profile_id = uuid.uuid4()
        profile = UserModel(
            id=profile_id,
            organization_id=organization.id,
            full_name="Document Processing Integration Test User",
            email=f"doc-processing-integration-{profile_id}@example.com",
            role="admin",
        )
        session.add(profile)
        await session.commit()
        cleanup_ids["users"].append(profile_id)

        return organization.id, engagement.id, profile_id


async def _make_document(
    cleanup_ids: dict[str, list[uuid.UUID]],
    engagement_id: uuid.UUID,
    *,
    status: str = "PENDING",
) -> tuple[uuid.UUID, str]:
    storage_path = f"test/{uuid.uuid4()}.pdf"
    async with AsyncSessionLocal() as session:
        document = DocumentModel(
            filename="sustainability-report.pdf",
            storage_path=storage_path,
            processing_status=status,
            engagement_id=engagement_id,
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
    cleanup_ids["documents"].append(document.id)
    return document.id, storage_path


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


async def test_successful_processing_persists_extracted_text_and_chunks(
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
    document_id, storage_path = await _make_document(cleanup_ids, engagement_id)
    fake_storage.seed(storage_path, _make_pdf_bytes("Real ESG disclosure content for processing."))
    token = _token_for(private_key, real_verifier, profile_id)

    response = await client.post(
        f"/api/v1/documents/{document_id}/process",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["processing_status"] == "PROCESSED"
    assert set(body.keys()) == {
        "id",
        "engagement_id",
        "filename",
        "processing_status",
        "created_at",
        "updated_at",
    }

    async with AsyncSessionLocal() as verify_session:
        document_model = await verify_session.get(DocumentModel, document_id)
        assert document_model is not None
        assert document_model.processing_status == "PROCESSED"

        text_result = await verify_session.execute(
            select(ExtractedTextModel).where(ExtractedTextModel.document_id == document_id)
        )
        text_rows = text_result.scalars().all()
        assert len(text_rows) == 1
        cleanup_ids["extracted_text"].append(text_rows[0].id)
        assert "Real ESG disclosure content" in (text_rows[0].extracted_content or "")

        chunk_result = await verify_session.execute(
            select(DocumentChunkModel).where(DocumentChunkModel.document_id == document_id)
        )
        chunk_rows = chunk_result.scalars().all()
        assert len(chunk_rows) >= 1
        cleanup_ids["chunks"].extend(c.id for c in chunk_rows)
        chunk_indexes = sorted(c.chunk_index for c in chunk_rows)
        assert chunk_indexes == list(range(len(chunk_indexes)))  # sequential, no duplicates


async def test_organization_mismatch_returns_403_and_leaves_document_untouched(
    client: AsyncClient,
    keypair,
    real_verifier: SupabaseJWTVerifier,
    fake_storage: FakeDocumentStorage,
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> None:
    private_key, _public_key = keypair
    _organization_id, engagement_id, _profile_id = await _make_organization_engagement_and_profile(
        cleanup_ids
    )
    document_id, storage_path = await _make_document(cleanup_ids, engagement_id)
    fake_storage.seed(storage_path, _make_pdf_bytes("Should never be processed."))

    async with AsyncSessionLocal() as session:
        other_organization = OrganizationModel(name="Document Processing Integration Test Other Org")
        session.add(other_organization)
        await session.flush()
        cleanup_ids["organizations"].append(other_organization.id)

        other_profile_id = uuid.uuid4()
        other_profile = UserModel(
            id=other_profile_id,
            organization_id=other_organization.id,
            full_name="Other Org User",
            email=f"other-org-processing-{other_profile_id}@example.com",
            role="admin",
        )
        session.add(other_profile)
        await session.commit()
        cleanup_ids["users"].append(other_profile_id)

    token = _token_for(private_key, real_verifier, other_profile_id)

    response = await client.post(
        f"/api/v1/documents/{document_id}/process",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403

    async with AsyncSessionLocal() as verify_session:
        document_model = await verify_session.get(DocumentModel, document_id)
        assert document_model is not None
        assert document_model.processing_status == "PENDING"  # never claimed

        text_result = await verify_session.execute(
            select(ExtractedTextModel).where(ExtractedTextModel.document_id == document_id)
        )
        assert text_result.scalars().all() == []
        chunk_result = await verify_session.execute(
            select(DocumentChunkModel).where(DocumentChunkModel.document_id == document_id)
        )
        assert chunk_result.scalars().all() == []


async def test_missing_document_returns_404(
    client: AsyncClient,
    keypair,
    real_verifier: SupabaseJWTVerifier,
    cleanup_ids: dict[str, list[uuid.UUID]],
) -> None:
    private_key, _public_key = keypair
    _organization_id, _engagement_id, profile_id = await _make_organization_engagement_and_profile(
        cleanup_ids
    )
    token = _token_for(private_key, real_verifier, profile_id)

    response = await client.post(
        f"/api/v1/documents/{uuid.uuid4()}/process",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


async def test_reprocessing_an_already_processed_document_returns_409(
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
    document_id, storage_path = await _make_document(cleanup_ids, engagement_id)
    fake_storage.seed(storage_path, _make_pdf_bytes("Processed exactly once."))
    token = _token_for(private_key, real_verifier, profile_id)

    first_response = await client.post(
        f"/api/v1/documents/{document_id}/process",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first_response.status_code == 200

    async with AsyncSessionLocal() as verify_session:
        text_result = await verify_session.execute(
            select(ExtractedTextModel).where(ExtractedTextModel.document_id == document_id)
        )
        text_rows = text_result.scalars().all()
        cleanup_ids["extracted_text"].extend(row.id for row in text_rows)
        chunk_result = await verify_session.execute(
            select(DocumentChunkModel).where(DocumentChunkModel.document_id == document_id)
        )
        chunk_rows = chunk_result.scalars().all()
        cleanup_ids["chunks"].extend(row.id for row in chunk_rows)

    second_response = await client.post(
        f"/api/v1/documents/{document_id}/process",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Document has already been processed."

    # No duplicate rows were created by the rejected second attempt.
    async with AsyncSessionLocal() as verify_session:
        text_result = await verify_session.execute(
            select(ExtractedTextModel).where(ExtractedTextModel.document_id == document_id)
        )
        assert len(text_result.scalars().all()) == 1
