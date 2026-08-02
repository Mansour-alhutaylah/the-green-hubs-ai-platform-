"""Unit tests for ``DocumentReadService`` -- business logic exercised
against in-memory fake repositories. No database, no HTTP, no
``integration`` mark.

Mirrors ``test_engagement_service.py``'s shape: two organizations
(A/B), two users (one per organization), same-tenant success and
cross-tenant denial exercised for both ``list`` and ``get``.
"""

import uuid
from datetime import datetime, timezone
from typing import Sequence

import pytest

from app.core.exceptions import AuthorizationError, NotFoundError
from app.domain.entities.document_read_model import (
    AnalysisSummary,
    DocumentReadModel,
    EmbeddingSummary,
)
from app.domain.entities.engagement import Engagement
from app.domain.entities.user import User
from app.domain.repositories.document import IDocumentRepository
from app.domain.repositories.engagement import IEngagementRepository
from app.services.document_read import DocumentReadService

_EMPTY_EMBEDDING_SUMMARY = EmbeddingSummary(
    total_chunks=0, processing=0, completed=0, failed=0, is_complete=False
)


def _read_model(
    *,
    engagement_id: uuid.UUID,
    created_at: datetime | None = None,
    processing_status: str = "PROCESSED",
) -> DocumentReadModel:
    return DocumentReadModel(
        id=uuid.uuid4(),
        engagement_id=engagement_id,
        filename="report.pdf",
        processing_status=processing_status,
        created_at=created_at or datetime.now(timezone.utc),
        updated_at=created_at or datetime.now(timezone.utc),
        has_extracted_text=True,
        chunk_count=3,
        embedding_summary=_EMPTY_EMBEDDING_SUMMARY,
        latest_analysis_summary=None,
    )


class FakeDocumentRepository(IDocumentRepository):
    """Only implements the read-model methods ``DocumentReadService``
    actually calls -- every write/legacy method is intentionally
    unimplemented, since a bug that routed a read-service call through
    them would be a real defect worth surfacing loudly."""

    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, tuple[DocumentReadModel, uuid.UUID]] = {}
        self.list_calls: list[dict] = []
        self.count_calls: list[dict] = []
        self.get_calls: list[dict] = []

    def seed(self, document: DocumentReadModel, *, organization_id: uuid.UUID) -> DocumentReadModel:
        self.rows[document.id] = (document, organization_id)
        return document

    async def get_read_model_for_organization(
        self,
        document_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        embedding_provider: str,
        embedding_model: str,
        embedding_model_version: str,
    ) -> DocumentReadModel | None:
        self.get_calls.append(
            {
                "document_id": document_id,
                "organization_id": organization_id,
                "embedding_provider": embedding_provider,
                "embedding_model": embedding_model,
                "embedding_model_version": embedding_model_version,
            }
        )
        entry = self.rows.get(document_id)
        if entry is None:
            return None
        document, owner_organization_id = entry
        if owner_organization_id != organization_id:
            return None
        return document

    async def list_read_models_for_organization(
        self,
        *,
        organization_id: uuid.UUID,
        engagement_id: uuid.UUID | None = None,
        processing_status: str | None = None,
        limit: int,
        offset: int,
        embedding_provider: str,
        embedding_model: str,
        embedding_model_version: str,
    ) -> Sequence[DocumentReadModel]:
        self.list_calls.append(
            {
                "organization_id": organization_id,
                "engagement_id": engagement_id,
                "processing_status": processing_status,
                "limit": limit,
                "offset": offset,
                "embedding_provider": embedding_provider,
                "embedding_model": embedding_model,
                "embedding_model_version": embedding_model_version,
            }
        )
        matches = [
            document
            for document, owner_organization_id in self.rows.values()
            if owner_organization_id == organization_id
            and (engagement_id is None or document.engagement_id == engagement_id)
            and (processing_status is None or document.processing_status == processing_status)
        ]
        matches.sort(key=lambda d: (d.created_at, str(d.id)), reverse=True)
        return matches[offset : offset + limit]

    async def count_for_organization(
        self,
        *,
        organization_id: uuid.UUID,
        engagement_id: uuid.UUID | None = None,
        processing_status: str | None = None,
    ) -> int:
        self.count_calls.append(
            {
                "organization_id": organization_id,
                "engagement_id": engagement_id,
                "processing_status": processing_status,
            }
        )
        return len(
            [
                document
                for document, owner_organization_id in self.rows.values()
                if owner_organization_id == organization_id
                and (engagement_id is None or document.engagement_id == engagement_id)
                and (processing_status is None or document.processing_status == processing_status)
            ]
        )

    # -- Unused by DocumentReadService; kept only to satisfy the ABC. --
    async def get(self, entity_id):  # type: ignore[override]
        raise NotImplementedError

    async def list(self, *, limit: int = 100, offset: int = 0):  # type: ignore[override]
        raise NotImplementedError

    async def create(self, entity):  # type: ignore[override]
        raise NotImplementedError

    async def update(self, entity):  # type: ignore[override]
        raise NotImplementedError

    async def delete(self, entity):  # type: ignore[override]
        raise NotImplementedError

    async def get_by_engagement(self, engagement_id):  # type: ignore[override]
        raise NotImplementedError

    async def update_status(self, document_id, status):  # type: ignore[override]
        raise NotImplementedError

    async def begin_processing(self, document_id):  # type: ignore[override]
        raise NotImplementedError

    async def complete_processing(self, document_id):  # type: ignore[override]
        raise NotImplementedError


class FakeEngagementRepository(IEngagementRepository):
    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, Engagement] = {}

    def seed(self, organization_id: uuid.UUID) -> Engagement:
        engagement_id = uuid.uuid4()
        engagement = Engagement(
            id=engagement_id,
            organization_id=organization_id,
            title="Seed Engagement",
            status="planning",
            created_at=datetime.now(timezone.utc),
        )
        self._rows[engagement_id] = engagement
        return engagement

    async def get(self, entity_id):  # type: ignore[override]
        return self._rows.get(entity_id)

    async def list(self, *, limit: int = 100, offset: int = 0, organization_id=None):  # type: ignore[override]
        raise NotImplementedError

    async def count(self, *, organization_id):  # type: ignore[override]
        raise NotImplementedError

    async def get_for_organization(
        self, entity_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Engagement | None:
        row = self._rows.get(entity_id)
        if row is not None and row.organization_id == organization_id:
            return row
        return None

    async def update_for_organization(self, entity, *, organization_id):  # type: ignore[override]
        raise NotImplementedError

    async def create(self, entity):  # type: ignore[override]
        raise NotImplementedError

    async def update(self, entity):  # type: ignore[override]
        raise NotImplementedError

    async def delete(self, entity):  # type: ignore[override]
        raise NotImplementedError


def _user(organization_id: uuid.UUID | None) -> User:
    return User(
        id=uuid.uuid4(),
        organization_id=organization_id,
        full_name="Test User",
        email="test@example.com",
        role=None,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def document_repository() -> FakeDocumentRepository:
    return FakeDocumentRepository()


@pytest.fixture
def engagement_repository() -> FakeEngagementRepository:
    return FakeEngagementRepository()


_EMBEDDING_PROVIDER = "openai"
_EMBEDDING_MODEL = "text-embedding-3-small"
_EMBEDDING_MODEL_VERSION = ""


@pytest.fixture
def service(
    document_repository: FakeDocumentRepository, engagement_repository: FakeEngagementRepository
) -> DocumentReadService:
    return DocumentReadService(
        document_repository,
        engagement_repository,
        embedding_provider=_EMBEDDING_PROVIDER,
        embedding_model=_EMBEDDING_MODEL,
        embedding_model_version=_EMBEDDING_MODEL_VERSION,
    )


@pytest.fixture
def organization_a_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def organization_b_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def user_a(organization_a_id: uuid.UUID) -> User:
    return _user(organization_a_id)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


async def test_list_automatically_scopes_to_own_organization(
    service: DocumentReadService,
    document_repository: FakeDocumentRepository,
    user_a: User,
    organization_a_id: uuid.UUID,
    organization_b_id: uuid.UUID,
) -> None:
    own = _read_model(engagement_id=uuid.uuid4())
    document_repository.seed(own, organization_id=organization_a_id)
    document_repository.seed(_read_model(engagement_id=uuid.uuid4()), organization_id=organization_b_id)

    items, total = await service.list(
        user_a, engagement_id=None, processing_status=None, limit=20, offset=0
    )

    assert total == 1
    assert [item.id for item in items] == [own.id]


async def test_list_rejected_for_user_with_null_organization(service: DocumentReadService) -> None:
    user = _user(None)
    with pytest.raises(AuthorizationError):
        await service.list(user, engagement_id=None, processing_status=None, limit=20, offset=0)


async def test_list_empty_returns_no_items_and_zero_total(
    service: DocumentReadService, user_a: User
) -> None:
    items, total = await service.list(
        user_a, engagement_id=None, processing_status=None, limit=20, offset=0
    )

    assert items == []
    assert total == 0


async def test_list_with_own_engagement_filter_succeeds(
    service: DocumentReadService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    user_a: User,
    organization_a_id: uuid.UUID,
) -> None:
    engagement = engagement_repository.seed(organization_a_id)
    matching = _read_model(engagement_id=engagement.id)  # type: ignore[arg-type]
    document_repository.seed(matching, organization_id=organization_a_id)
    document_repository.seed(_read_model(engagement_id=uuid.uuid4()), organization_id=organization_a_id)

    items, total = await service.list(
        user_a, engagement_id=engagement.id, processing_status=None, limit=20, offset=0
    )

    assert total == 1
    assert items[0].id == matching.id


async def test_list_with_foreign_engagement_filter_raises_not_found(
    service: DocumentReadService,
    engagement_repository: FakeEngagementRepository,
    user_a: User,
    organization_b_id: uuid.UUID,
) -> None:
    foreign_engagement = engagement_repository.seed(organization_b_id)

    with pytest.raises(NotFoundError):
        await service.list(
            user_a,
            engagement_id=foreign_engagement.id,
            processing_status=None,
            limit=20,
            offset=0,
        )


async def test_list_with_missing_engagement_filter_raises_not_found(
    service: DocumentReadService, user_a: User
) -> None:
    with pytest.raises(NotFoundError):
        await service.list(
            user_a, engagement_id=uuid.uuid4(), processing_status=None, limit=20, offset=0
        )


async def test_list_forwards_processing_status_filter(
    service: DocumentReadService, document_repository: FakeDocumentRepository, user_a: User, organization_a_id: uuid.UUID
) -> None:
    document_repository.seed(
        _read_model(engagement_id=uuid.uuid4(), processing_status="FAILED"),
        organization_id=organization_a_id,
    )
    document_repository.seed(
        _read_model(engagement_id=uuid.uuid4(), processing_status="PROCESSED"),
        organization_id=organization_a_id,
    )

    items, total = await service.list(
        user_a, engagement_id=None, processing_status="FAILED", limit=20, offset=0
    )

    assert total == 1
    assert items[0].processing_status == "FAILED"


async def test_list_forwards_the_current_embedding_identity_to_the_repository(
    service: DocumentReadService, document_repository: FakeDocumentRepository, user_a: User
) -> None:
    """The embedding identity forwarded here is what scopes each
    document's ``embedding_summary`` to only the app's currently
    configured (provider, model, model_version) -- so it must reach the
    repository call, not be silently dropped."""
    await service.list(user_a, engagement_id=None, processing_status=None, limit=20, offset=0)

    call = document_repository.list_calls[-1]
    assert call["embedding_provider"] == _EMBEDDING_PROVIDER
    assert call["embedding_model"] == _EMBEDDING_MODEL
    assert call["embedding_model_version"] == _EMBEDDING_MODEL_VERSION


async def test_list_forwards_pagination_to_repository(
    service: DocumentReadService, document_repository: FakeDocumentRepository, user_a: User
) -> None:
    await service.list(user_a, engagement_id=None, processing_status=None, limit=5, offset=10)

    assert document_repository.list_calls[-1]["limit"] == 5
    assert document_repository.list_calls[-1]["offset"] == 10
    assert document_repository.count_calls[-1]["organization_id"] == user_a.organization_id


async def test_list_returns_newest_first(
    service: DocumentReadService,
    document_repository: FakeDocumentRepository,
    user_a: User,
    organization_a_id: uuid.UUID,
) -> None:
    older = _read_model(engagement_id=uuid.uuid4(), created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    newer = _read_model(engagement_id=uuid.uuid4(), created_at=datetime(2026, 6, 1, tzinfo=timezone.utc))
    document_repository.seed(older, organization_id=organization_a_id)
    document_repository.seed(newer, organization_id=organization_a_id)

    items, _ = await service.list(
        user_a, engagement_id=None, processing_status=None, limit=20, offset=0
    )

    assert [item.id for item in items] == [newer.id, older.id]


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


async def test_get_own_document_succeeds(
    service: DocumentReadService,
    document_repository: FakeDocumentRepository,
    user_a: User,
    organization_a_id: uuid.UUID,
) -> None:
    document = _read_model(engagement_id=uuid.uuid4())
    document_repository.seed(document, organization_id=organization_a_id)

    fetched = await service.get(document.id, user_a)

    assert fetched.id == document.id


async def test_get_another_tenants_document_returns_not_found(
    service: DocumentReadService,
    document_repository: FakeDocumentRepository,
    user_a: User,
    organization_b_id: uuid.UUID,
) -> None:
    document = _read_model(engagement_id=uuid.uuid4())
    document_repository.seed(document, organization_id=organization_b_id)

    with pytest.raises(NotFoundError):
        await service.get(document.id, user_a)


async def test_get_missing_document_returns_identical_not_found(
    service: DocumentReadService, user_a: User
) -> None:
    with pytest.raises(NotFoundError):
        await service.get(uuid.uuid4(), user_a)


async def test_get_rejected_for_user_with_null_organization(service: DocumentReadService) -> None:
    user = _user(None)
    with pytest.raises(AuthorizationError):
        await service.get(uuid.uuid4(), user)


async def test_get_forwards_the_current_embedding_identity_to_the_repository(
    service: DocumentReadService,
    document_repository: FakeDocumentRepository,
    user_a: User,
    organization_a_id: uuid.UUID,
) -> None:
    document = _read_model(engagement_id=uuid.uuid4())
    document_repository.seed(document, organization_id=organization_a_id)

    await service.get(document.id, user_a)

    call = document_repository.get_calls[-1]
    assert call["embedding_provider"] == _EMBEDDING_PROVIDER
    assert call["embedding_model"] == _EMBEDDING_MODEL
    assert call["embedding_model_version"] == _EMBEDDING_MODEL_VERSION


async def test_get_maps_embedding_and_analysis_summaries_through_untouched(
    service: DocumentReadService,
    document_repository: FakeDocumentRepository,
    user_a: User,
    organization_a_id: uuid.UUID,
) -> None:
    analysis_summary = AnalysisSummary(
        id=uuid.uuid4(),
        status="COMPLETED",
        analysis_type="sustainability_summary",
        created_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        overall_confidence=0.87,
    )
    embedding_summary = EmbeddingSummary(
        total_chunks=4, processing=0, completed=4, failed=0, is_complete=True
    )
    document = DocumentReadModel(
        id=uuid.uuid4(),
        engagement_id=uuid.uuid4(),
        filename="report.pdf",
        processing_status="PROCESSED",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        has_extracted_text=True,
        chunk_count=4,
        embedding_summary=embedding_summary,
        latest_analysis_summary=analysis_summary,
    )
    document_repository.seed(document, organization_id=organization_a_id)

    fetched = await service.get(document.id, user_a)

    assert fetched.embedding_summary == embedding_summary
    assert fetched.latest_analysis_summary == analysis_summary
