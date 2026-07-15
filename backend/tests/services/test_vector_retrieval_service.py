"""Unit tests for ``VectorRetrievalService`` -- business logic exercised
against in-memory fakes. No database, no network, no ``integration`` mark.
"""

import uuid
from datetime import datetime, timezone
from typing import Sequence

import pytest

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.domain.embedding_provider import EmbeddingProvider, EmbeddingResult
from app.domain.entities.document import Document
from app.domain.entities.engagement import Engagement
from app.domain.entities.user import User
from app.domain.entities.vector_search_result import VectorSearchResult
from app.domain.repositories.document import IDocumentRepository
from app.domain.repositories.document_chunk_embedding import IDocumentChunkEmbeddingRepository
from app.domain.repositories.engagement import IEngagementRepository
from app.services.vector_retrieval import VectorRetrievalService

PROVIDER_NAME = "openai"
MODEL = "text-embedding-3-small"
MODEL_VERSION = ""
DIMENSION = 1536


class FakeDocumentRepository(IDocumentRepository):
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, Document] = {}

    def seed(self, document: Document) -> None:
        self.rows[document.id] = document

    async def get(self, entity_id: uuid.UUID) -> Document | None:
        return self.rows.get(entity_id)

    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[Document]:
        return list(self.rows.values())

    async def create(self, entity: Document) -> Document:
        raise NotImplementedError

    async def update(self, entity: Document) -> Document:
        raise NotImplementedError

    async def delete(self, entity: Document) -> None:
        raise NotImplementedError

    async def get_by_engagement(self, engagement_id: uuid.UUID) -> Sequence[Document]:
        return [d for d in self.rows.values() if d.engagement_id == engagement_id]

    async def update_status(self, document_id: uuid.UUID, status: str) -> Document:
        raise NotImplementedError

    async def begin_processing(self, document_id: uuid.UUID) -> Document:
        raise NotImplementedError

    async def complete_processing(self, document_id: uuid.UUID) -> Document:
        raise NotImplementedError

    async def get_read_model_for_organization(self, document_id: uuid.UUID, *, organization_id: uuid.UUID):
        raise NotImplementedError

    async def list_read_models_for_organization(self, *, organization_id: uuid.UUID, engagement_id=None, processing_status=None, limit: int, offset: int):
        raise NotImplementedError

    async def count_for_organization(self, *, organization_id: uuid.UUID, engagement_id=None, processing_status=None) -> int:
        raise NotImplementedError


class FakeEngagementRepository(IEngagementRepository):
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, Engagement] = {}

    def seed(self, engagement: Engagement) -> None:
        assert engagement.id is not None
        self.rows[engagement.id] = engagement

    async def get(self, entity_id: uuid.UUID) -> Engagement | None:
        return self.rows.get(entity_id)

    async def list(
        self, *, limit: int = 100, offset: int = 0, organization_id: uuid.UUID | None = None
    ) -> Sequence[Engagement]:
        return list(self.rows.values())

    async def count(self, *, organization_id: uuid.UUID) -> int:
        return len(self.rows)

    async def get_for_organization(
        self, entity_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Engagement | None:
        row = self.rows.get(entity_id)
        return row if row is not None and row.organization_id == organization_id else None

    async def update_for_organization(
        self, entity: Engagement, *, organization_id: uuid.UUID
    ) -> Engagement:
        raise NotImplementedError

    async def create(self, entity: Engagement) -> Engagement:
        raise NotImplementedError

    async def update(self, entity: Engagement) -> Engagement:
        raise NotImplementedError

    async def delete(self, entity: Engagement) -> None:
        raise NotImplementedError


class FakeDocumentChunkEmbeddingRepository(IDocumentChunkEmbeddingRepository):
    def __init__(self) -> None:
        self.search_calls: list[dict] = []
        self.results: list[VectorSearchResult] = []

    async def claim_new(self, *args: object, **kwargs: object) -> Sequence:  # type: ignore[type-arg]
        raise NotImplementedError

    async def get_existing(self, *args: object, **kwargs: object) -> Sequence:  # type: ignore[type-arg]
        raise NotImplementedError

    async def retry_failed(self, *args: object, **kwargs: object) -> Sequence:  # type: ignore[type-arg]
        raise NotImplementedError

    async def reclaim_stale(self, *args: object, **kwargs: object) -> Sequence:  # type: ignore[type-arg]
        raise NotImplementedError

    async def mark_completed(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError

    async def mark_failed(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError

    async def search(
        self,
        *,
        organization_id: uuid.UUID,
        provider: str,
        model: str,
        model_version: str,
        query_vector: Sequence[float],
        top_k: int,
        engagement_id: uuid.UUID | None = None,
        document_id: uuid.UUID | None = None,
    ) -> Sequence[VectorSearchResult]:
        self.search_calls.append(
            {
                "organization_id": organization_id,
                "provider": provider,
                "model": model,
                "model_version": model_version,
                "query_vector": query_vector,
                "top_k": top_k,
                "engagement_id": engagement_id,
                "document_id": document_id,
            }
        )
        return self.results

    async def delete(self, entity: object) -> None:
        raise NotImplementedError


class FakeEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed_texts(self, texts: Sequence[str]) -> Sequence[EmbeddingResult]:
        self.calls.append(list(texts))
        return [
            EmbeddingResult(text=t, vector=[0.2] * DIMENSION, dimension=DIMENSION) for t in texts
        ]


def _user(organization_id: uuid.UUID | None) -> User:
    return User(
        id=uuid.uuid4(), organization_id=organization_id, full_name="Test User",
        email="test@example.com", role=None, created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def document_repository() -> FakeDocumentRepository:
    return FakeDocumentRepository()


@pytest.fixture
def engagement_repository() -> FakeEngagementRepository:
    return FakeEngagementRepository()


@pytest.fixture
def embedding_repository() -> FakeDocumentChunkEmbeddingRepository:
    return FakeDocumentChunkEmbeddingRepository()


@pytest.fixture
def provider() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest.fixture
def service(
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
    engagement_repository: FakeEngagementRepository,
    document_repository: FakeDocumentRepository,
    provider: FakeEmbeddingProvider,
) -> VectorRetrievalService:
    return VectorRetrievalService(
        embedding_repository, engagement_repository, document_repository, provider,
        provider_name=PROVIDER_NAME, model=MODEL, model_version=MODEL_VERSION,
    )


async def test_null_organization_rejected_with_403(service: VectorRetrievalService) -> None:
    user = _user(None)
    with pytest.raises(AuthorizationError):
        await service.search(user, query="emissions", top_k=5)


async def test_empty_query_rejected_with_422(service: VectorRetrievalService) -> None:
    user = _user(uuid.uuid4())
    with pytest.raises(ValidationError):
        await service.search(user, query="   ", top_k=5)


@pytest.mark.parametrize("top_k", [0, -1, 51, 1000])
async def test_invalid_top_k_rejected_with_422(
    service: VectorRetrievalService, top_k: int
) -> None:
    user = _user(uuid.uuid4())
    with pytest.raises(ValidationError):
        await service.search(user, query="emissions", top_k=top_k)


async def test_derives_organization_id_from_current_user_only(
    service: VectorRetrievalService,
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
) -> None:
    organization_id = uuid.uuid4()
    user = _user(organization_id)

    await service.search(user, query="emissions", top_k=5)

    assert embedding_repository.search_calls[0]["organization_id"] == organization_id


async def test_creates_query_embedding_through_provider(
    service: VectorRetrievalService, provider: FakeEmbeddingProvider
) -> None:
    user = _user(uuid.uuid4())

    await service.search(user, query="scope 1 emissions", top_k=5)

    assert provider.calls == [["scope 1 emissions"]]


async def test_inaccessible_engagement_filter_returns_404(
    service: VectorRetrievalService,
    engagement_repository: FakeEngagementRepository,
) -> None:
    other_org_engagement = Engagement(
        id=uuid.uuid4(), organization_id=uuid.uuid4(), title="Other", status="planning",
        created_at=datetime.now(timezone.utc),
    )
    engagement_repository.seed(other_org_engagement)
    user = _user(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await service.search(
            user, query="emissions", top_k=5, engagement_id=other_org_engagement.id
        )


async def test_missing_engagement_filter_returns_404(service: VectorRetrievalService) -> None:
    user = _user(uuid.uuid4())
    with pytest.raises(NotFoundError):
        await service.search(user, query="emissions", top_k=5, engagement_id=uuid.uuid4())


async def test_inaccessible_document_filter_returns_404(
    service: VectorRetrievalService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
) -> None:
    other_engagement = Engagement(
        id=uuid.uuid4(), organization_id=uuid.uuid4(), title="Other", status="planning",
        created_at=datetime.now(timezone.utc),
    )
    engagement_repository.seed(other_engagement)
    now = datetime.now(timezone.utc)
    other_document = Document(
        id=uuid.uuid4(), filename="x.pdf", storage_path="x", processing_status="PROCESSED",
        engagement_id=other_engagement.id, created_at=now, updated_at=now,
    )
    document_repository.seed(other_document)
    user = _user(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await service.search(user, query="emissions", top_k=5, document_id=other_document.id)


async def test_missing_document_filter_returns_404(service: VectorRetrievalService) -> None:
    user = _user(uuid.uuid4())
    with pytest.raises(NotFoundError):
        await service.search(user, query="emissions", top_k=5, document_id=uuid.uuid4())


async def test_document_not_belonging_to_supplied_engagement_rejected_with_422(
    service: VectorRetrievalService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
) -> None:
    organization_id = uuid.uuid4()
    engagement_a = Engagement(
        id=uuid.uuid4(), organization_id=organization_id, title="A", status="planning",
        created_at=datetime.now(timezone.utc),
    )
    engagement_b = Engagement(
        id=uuid.uuid4(), organization_id=organization_id, title="B", status="planning",
        created_at=datetime.now(timezone.utc),
    )
    engagement_repository.seed(engagement_a)
    engagement_repository.seed(engagement_b)
    now = datetime.now(timezone.utc)
    document = Document(
        id=uuid.uuid4(), filename="x.pdf", storage_path="x", processing_status="PROCESSED",
        engagement_id=engagement_a.id, created_at=now, updated_at=now,
    )
    document_repository.seed(document)
    user = _user(organization_id)

    with pytest.raises(ValidationError):
        await service.search(
            user, query="emissions", top_k=5, engagement_id=engagement_b.id,
            document_id=document.id,
        )


async def test_consistent_engagement_and_document_filters_both_passed_through(
    service: VectorRetrievalService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
) -> None:
    organization_id = uuid.uuid4()
    engagement = Engagement(
        id=uuid.uuid4(), organization_id=organization_id, title="A", status="planning",
        created_at=datetime.now(timezone.utc),
    )
    engagement_repository.seed(engagement)
    now = datetime.now(timezone.utc)
    document = Document(
        id=uuid.uuid4(), filename="x.pdf", storage_path="x", processing_status="PROCESSED",
        engagement_id=engagement.id, created_at=now, updated_at=now,
    )
    document_repository.seed(document)
    user = _user(organization_id)

    await service.search(
        user, query="emissions", top_k=5, engagement_id=engagement.id, document_id=document.id
    )

    call = embedding_repository.search_calls[0]
    assert call["engagement_id"] == engagement.id
    assert call["document_id"] == document.id


async def test_returns_results_from_repository_unchanged(
    service: VectorRetrievalService,
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
) -> None:
    expected = [
        VectorSearchResult(
            chunk_id=uuid.uuid4(), document_id=uuid.uuid4(), engagement_id=uuid.uuid4(),
            chunk_index=0, content="Scope 1 emissions increased.", char_start=0, char_end=28,
            similarity_score=0.93,
        )
    ]
    embedding_repository.results = expected
    user = _user(uuid.uuid4())

    results = await service.search(user, query="emissions", top_k=5)

    assert list(results) == expected
