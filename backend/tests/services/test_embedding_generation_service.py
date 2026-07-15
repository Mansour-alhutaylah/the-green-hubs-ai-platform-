"""Unit tests for ``EmbeddingGenerationService`` -- business logic exercised
against in-memory fakes. No database, no network, no ``integration`` mark.
"""

import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Mapping, Sequence

import pytest

from app.core.exceptions import AuthorizationError, InvalidStateTransitionError, NotFoundError
from app.domain.embedding_provider import EmbeddingProvider, EmbeddingProviderUnavailableError, EmbeddingResult
from app.domain.entities.document import Document
from app.domain.entities.document_chunk import DocumentChunk
from app.domain.entities.document_chunk_embedding import DocumentChunkEmbedding
from app.domain.entities.engagement import Engagement
from app.domain.entities.user import User
from app.domain.entities.vector_search_result import VectorSearchResult
from app.domain.repositories.document import IDocumentRepository
from app.domain.repositories.document_chunk import IDocumentChunkRepository
from app.domain.repositories.document_chunk_embedding import IDocumentChunkEmbeddingRepository
from app.domain.repositories.engagement import IEngagementRepository
from app.services.embedding_generation import EmbeddingGenerationService, _content_hash

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


class FakeDocumentChunkRepository(IDocumentChunkRepository):
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, list[DocumentChunk]] = {}

    def seed(self, document_id: uuid.UUID, chunks: list[DocumentChunk]) -> None:
        self.rows[document_id] = chunks

    async def create_many(self, entities: Sequence[DocumentChunk]) -> Sequence[DocumentChunk]:
        raise NotImplementedError

    async def get_by_document(self, document_id: uuid.UUID) -> Sequence[DocumentChunk]:
        return self.rows.get(document_id, [])

    async def delete(self, entity: DocumentChunk) -> None:
        raise NotImplementedError


class FakeDocumentChunkEmbeddingRepository(IDocumentChunkEmbeddingRepository):
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, DocumentChunkEmbedding] = {}
        self.chunk_lineage: dict[uuid.UUID, tuple[uuid.UUID, uuid.UUID, uuid.UUID]] = {}
        self.claim_new_calls: list[list[uuid.UUID]] = []

    def set_lineage(
        self, chunk_id: uuid.UUID, document_id: uuid.UUID, engagement_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        self.chunk_lineage[chunk_id] = (document_id, engagement_id, organization_id)

    def seed_row(
        self,
        chunk_id: uuid.UUID,
        *,
        status: str,
        content_hash: str,
        processing_started_at: datetime | None = None,
        attempt_count: int = 1,
    ) -> DocumentChunkEmbedding:
        document_id, engagement_id, organization_id = self.chunk_lineage[chunk_id]
        now = datetime.now(timezone.utc)
        row = DocumentChunkEmbedding(
            id=uuid.uuid4(),
            chunk_id=chunk_id,
            document_id=document_id,
            engagement_id=engagement_id,
            organization_id=organization_id,
            provider=PROVIDER_NAME,
            model=MODEL,
            model_version=MODEL_VERSION,
            embedding_dimension=DIMENSION,
            embedding=[0.1] * DIMENSION if status == "COMPLETED" else None,
            content_hash=content_hash,
            status=status,
            error_message=None,
            processing_started_at=processing_started_at or now,
            attempt_count=attempt_count,
            created_at=now,
            updated_at=now,
        )
        self.rows[row.id] = row
        return row

    async def claim_new(
        self,
        chunk_ids: Sequence[uuid.UUID],
        *,
        provider: str,
        model: str,
        model_version: str,
        embedding_dimension: int,
        content_hashes: Mapping[uuid.UUID, str],
    ) -> Sequence[DocumentChunkEmbedding]:
        self.claim_new_calls.append(list(chunk_ids))
        claimed = []
        for chunk_id in chunk_ids:
            exists = any(
                r.chunk_id == chunk_id and r.provider == provider and r.model == model
                and r.model_version == model_version
                for r in self.rows.values()
            )
            if exists:
                continue
            document_id, engagement_id, organization_id = self.chunk_lineage[chunk_id]
            now = datetime.now(timezone.utc)
            row = DocumentChunkEmbedding(
                id=uuid.uuid4(), chunk_id=chunk_id, document_id=document_id,
                engagement_id=engagement_id, organization_id=organization_id,
                provider=provider, model=model, model_version=model_version,
                embedding_dimension=embedding_dimension, embedding=None,
                content_hash=content_hashes[chunk_id], status="PROCESSING", error_message=None,
                processing_started_at=now, attempt_count=1, created_at=now, updated_at=now,
            )
            self.rows[row.id] = row
            claimed.append(row)
        return claimed

    async def get_existing(
        self, chunk_ids: Sequence[uuid.UUID], *, provider: str, model: str, model_version: str
    ) -> Sequence[DocumentChunkEmbedding]:
        chunk_id_set = set(chunk_ids)
        return [
            r for r in self.rows.values()
            if r.chunk_id in chunk_id_set and r.provider == provider and r.model == model
            and r.model_version == model_version
        ]

    async def retry_failed(
        self, embedding_ids: Sequence[uuid.UUID]
    ) -> Sequence[DocumentChunkEmbedding]:
        retried = []
        for eid in embedding_ids:
            row = self.rows.get(eid)
            if row is not None and row.status == "FAILED":
                updated = replace(
                    row, status="PROCESSING", processing_started_at=datetime.now(timezone.utc),
                    attempt_count=row.attempt_count + 1, error_message=None,
                    updated_at=datetime.now(timezone.utc),
                )
                self.rows[eid] = updated
                retried.append(updated)
        return retried

    async def reclaim_stale(
        self, embedding_ids: Sequence[uuid.UUID], *, stale_after_seconds: int
    ) -> Sequence[DocumentChunkEmbedding]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)
        reclaimed = []
        for eid in embedding_ids:
            row = self.rows.get(eid)
            if (
                row is not None and row.status == "PROCESSING"
                and row.processing_started_at is not None and row.processing_started_at < cutoff
            ):
                updated = replace(
                    row, processing_started_at=datetime.now(timezone.utc),
                    attempt_count=row.attempt_count + 1, error_message=None,
                    updated_at=datetime.now(timezone.utc),
                )
                self.rows[eid] = updated
                reclaimed.append(updated)
        return reclaimed

    async def mark_completed(self, results: Sequence[tuple[uuid.UUID, Sequence[float]]]) -> None:
        for eid, vector in results:
            row = self.rows.get(eid)
            if row is not None:
                self.rows[eid] = replace(
                    row, status="COMPLETED", embedding=list(vector), error_message=None,
                    updated_at=datetime.now(timezone.utc),
                )

    async def mark_failed(self, embedding_ids: Sequence[uuid.UUID], *, error_message: str) -> None:
        for eid in embedding_ids:
            row = self.rows.get(eid)
            if row is not None:
                self.rows[eid] = replace(
                    row, status="FAILED", error_message=error_message,
                    updated_at=datetime.now(timezone.utc),
                )

    async def search(self, **kwargs: object) -> Sequence[VectorSearchResult]:
        raise NotImplementedError

    async def delete(self, entity: DocumentChunkEmbedding) -> None:
        if entity.id is not None:
            self.rows.pop(entity.id, None)


class FakeEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.error: Exception | None = None

    async def embed_texts(self, texts: Sequence[str]) -> Sequence[EmbeddingResult]:
        self.calls.append(list(texts))
        if self.error is not None:
            raise self.error
        return [
            EmbeddingResult(text=t, vector=[0.1] * DIMENSION, dimension=DIMENSION) for t in texts
        ]


def _user(organization_id: uuid.UUID | None) -> User:
    return User(
        id=uuid.uuid4(), organization_id=organization_id, full_name="Test User",
        email="test@example.com", role=None, created_at=datetime.now(timezone.utc),
    )


def _chunk(document_id: uuid.UUID, index: int, content: str) -> DocumentChunk:
    return DocumentChunk(
        id=uuid.uuid4(), document_id=document_id, chunk_index=index, content=content,
        char_start=0, char_end=len(content), created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def document_repository() -> FakeDocumentRepository:
    return FakeDocumentRepository()


@pytest.fixture
def engagement_repository() -> FakeEngagementRepository:
    return FakeEngagementRepository()


@pytest.fixture
def chunk_repository() -> FakeDocumentChunkRepository:
    return FakeDocumentChunkRepository()


@pytest.fixture
def embedding_repository() -> FakeDocumentChunkEmbeddingRepository:
    return FakeDocumentChunkEmbeddingRepository()


@pytest.fixture
def provider() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest.fixture
def service(
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    chunk_repository: FakeDocumentChunkRepository,
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
    provider: FakeEmbeddingProvider,
) -> EmbeddingGenerationService:
    return EmbeddingGenerationService(
        document_repository, engagement_repository, chunk_repository, embedding_repository,
        provider, provider_name=PROVIDER_NAME, model=MODEL, model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, max_batch_size=100, stale_after_seconds=300,
    )


def _setup_processed_document(
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    chunk_repository: FakeDocumentChunkRepository,
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
    *,
    num_chunks: int = 3,
    status: str = "PROCESSED",
) -> tuple[Document, list[DocumentChunk], User]:
    organization_id = uuid.uuid4()
    engagement = Engagement(
        id=uuid.uuid4(), organization_id=organization_id, title="Eng", status="planning",
        created_at=datetime.now(timezone.utc),
    )
    engagement_repository.seed(engagement)
    now = datetime.now(timezone.utc)
    document = Document(
        id=uuid.uuid4(), filename="report.pdf", storage_path="x/report.pdf",
        processing_status=status, engagement_id=engagement.id, created_at=now, updated_at=now,
    )
    document_repository.seed(document)
    chunks = [_chunk(document.id, i, f"chunk content number {i}") for i in range(num_chunks)]
    chunk_repository.seed(document.id, chunks)
    for chunk in chunks:
        assert chunk.id is not None
        embedding_repository.set_lineage(chunk.id, document.id, engagement.id, organization_id)
    user = _user(organization_id)
    return document, chunks, user


# ---------------------------------------------------------------------------
# Authorization / document state
# ---------------------------------------------------------------------------


async def test_missing_document_raises_not_found(service: EmbeddingGenerationService) -> None:
    user = _user(uuid.uuid4())
    with pytest.raises(NotFoundError):
        await service.generate_for_document(uuid.uuid4(), user)


async def test_null_user_organization_raises_authorization_error(
    service: EmbeddingGenerationService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    chunk_repository: FakeDocumentChunkRepository,
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
) -> None:
    document, _chunks, _user_a = _setup_processed_document(
        document_repository, engagement_repository, chunk_repository, embedding_repository
    )
    user = _user(None)
    with pytest.raises(AuthorizationError):
        await service.generate_for_document(document.id, user)


async def test_cross_tenant_document_returns_not_found(
    service: EmbeddingGenerationService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    chunk_repository: FakeDocumentChunkRepository,
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
) -> None:
    document, _chunks, _user_a = _setup_processed_document(
        document_repository, engagement_repository, chunk_repository, embedding_repository
    )
    other_user = _user(uuid.uuid4())
    with pytest.raises(NotFoundError):
        await service.generate_for_document(document.id, other_user)


async def test_unprocessed_document_raises_invalid_state_transition(
    service: EmbeddingGenerationService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    chunk_repository: FakeDocumentChunkRepository,
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
) -> None:
    document, _chunks, user = _setup_processed_document(
        document_repository, engagement_repository, chunk_repository, embedding_repository,
        status="PENDING",
    )
    with pytest.raises(InvalidStateTransitionError):
        await service.generate_for_document(document.id, user)


# ---------------------------------------------------------------------------
# Fresh generation
# ---------------------------------------------------------------------------


async def test_generates_embeddings_for_all_new_chunks(
    service: EmbeddingGenerationService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    chunk_repository: FakeDocumentChunkRepository,
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
    provider: FakeEmbeddingProvider,
) -> None:
    document, chunks, user = _setup_processed_document(
        document_repository, engagement_repository, chunk_repository, embedding_repository
    )

    summary = await service.generate_for_document(document.id, user)

    assert summary.total_chunks == 3
    assert summary.newly_completed == 3
    assert summary.already_completed == 0
    assert summary.failed == 0
    assert summary.in_progress == 0
    assert summary.conflicts == 0
    completed_rows = [r for r in embedding_repository.rows.values() if r.status == "COMPLETED"]
    assert len(completed_rows) == 3
    assert all(r.embedding is not None for r in completed_rows)
    assert len(provider.calls[0]) == 3


async def test_rerun_is_idempotent_and_does_not_recall_provider(
    service: EmbeddingGenerationService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    chunk_repository: FakeDocumentChunkRepository,
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
    provider: FakeEmbeddingProvider,
) -> None:
    document, _chunks, user = _setup_processed_document(
        document_repository, engagement_repository, chunk_repository, embedding_repository
    )
    await service.generate_for_document(document.id, user)
    provider.calls.clear()

    summary = await service.generate_for_document(document.id, user)

    assert summary.newly_completed == 0
    assert summary.already_completed == 3
    assert provider.calls == []


# ---------------------------------------------------------------------------
# FAILED retry
# ---------------------------------------------------------------------------


async def test_failed_row_with_matching_hash_is_retried(
    service: EmbeddingGenerationService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    chunk_repository: FakeDocumentChunkRepository,
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
) -> None:
    document, chunks, user = _setup_processed_document(
        document_repository, engagement_repository, chunk_repository, embedding_repository,
        num_chunks=1,
    )
    chunk = chunks[0]
    assert chunk.id is not None
    failed_row = embedding_repository.seed_row(
        chunk.id, status="FAILED", content_hash=_content_hash(chunk.content)
    )

    summary = await service.generate_for_document(document.id, user)

    assert summary.newly_completed == 1
    assert summary.failed == 0
    resolved = embedding_repository.rows[failed_row.id]
    assert resolved.status == "COMPLETED"
    assert resolved.attempt_count == 2  # incremented on retry


# ---------------------------------------------------------------------------
# Content-hash conflicts
# ---------------------------------------------------------------------------


async def test_completed_with_mismatched_hash_is_a_conflict_and_not_overwritten(
    service: EmbeddingGenerationService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    chunk_repository: FakeDocumentChunkRepository,
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
    provider: FakeEmbeddingProvider,
) -> None:
    document, chunks, user = _setup_processed_document(
        document_repository, engagement_repository, chunk_repository, embedding_repository,
        num_chunks=1,
    )
    chunk = chunks[0]
    assert chunk.id is not None
    stale_row = embedding_repository.seed_row(chunk.id, status="COMPLETED", content_hash="0" * 64)

    summary = await service.generate_for_document(document.id, user)

    assert summary.conflicts == 1
    assert summary.newly_completed == 0
    assert provider.calls == []
    untouched = embedding_repository.rows[stale_row.id]
    assert untouched.content_hash == "0" * 64  # never overwritten


async def test_failed_with_mismatched_hash_is_a_conflict_not_retried(
    service: EmbeddingGenerationService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    chunk_repository: FakeDocumentChunkRepository,
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
    provider: FakeEmbeddingProvider,
) -> None:
    document, chunks, user = _setup_processed_document(
        document_repository, engagement_repository, chunk_repository, embedding_repository,
        num_chunks=1,
    )
    chunk = chunks[0]
    assert chunk.id is not None
    embedding_repository.seed_row(chunk.id, status="FAILED", content_hash="0" * 64)

    summary = await service.generate_for_document(document.id, user)

    assert summary.conflicts == 1
    assert summary.failed == 0
    assert provider.calls == []


async def test_processing_with_mismatched_hash_is_a_conflict(
    service: EmbeddingGenerationService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    chunk_repository: FakeDocumentChunkRepository,
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
) -> None:
    document, chunks, user = _setup_processed_document(
        document_repository, engagement_repository, chunk_repository, embedding_repository,
        num_chunks=1,
    )
    chunk = chunks[0]
    assert chunk.id is not None
    embedding_repository.seed_row(chunk.id, status="PROCESSING", content_hash="0" * 64)

    summary = await service.generate_for_document(document.id, user)

    assert summary.conflicts == 1
    assert summary.in_progress == 0


# ---------------------------------------------------------------------------
# PROCESSING: in-progress vs. stale reclaim
# ---------------------------------------------------------------------------


async def test_non_stale_processing_row_is_reported_in_progress_and_never_embedded(
    service: EmbeddingGenerationService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    chunk_repository: FakeDocumentChunkRepository,
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
    provider: FakeEmbeddingProvider,
) -> None:
    document, chunks, user = _setup_processed_document(
        document_repository, engagement_repository, chunk_repository, embedding_repository,
        num_chunks=1,
    )
    chunk = chunks[0]
    assert chunk.id is not None
    embedding_repository.seed_row(
        chunk.id, status="PROCESSING", content_hash=_content_hash(chunk.content),
        processing_started_at=datetime.now(timezone.utc),  # fresh, not stale
    )

    summary = await service.generate_for_document(document.id, user)

    assert summary.in_progress == 1
    assert summary.newly_completed == 0
    assert provider.calls == []


async def test_stale_processing_row_is_reclaimed_and_embedded(
    service: EmbeddingGenerationService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    chunk_repository: FakeDocumentChunkRepository,
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
) -> None:
    document, chunks, user = _setup_processed_document(
        document_repository, engagement_repository, chunk_repository, embedding_repository,
        num_chunks=1,
    )
    chunk = chunks[0]
    assert chunk.id is not None
    stale_row = embedding_repository.seed_row(
        chunk.id, status="PROCESSING", content_hash=_content_hash(chunk.content),
        processing_started_at=datetime.now(timezone.utc) - timedelta(seconds=999),
    )

    summary = await service.generate_for_document(document.id, user)

    assert summary.newly_completed == 1
    assert summary.in_progress == 0
    resolved = embedding_repository.rows[stale_row.id]
    assert resolved.status == "COMPLETED"
    assert resolved.attempt_count == 2  # incremented on reclaim


# ---------------------------------------------------------------------------
# Batch success / failure semantics
# ---------------------------------------------------------------------------


async def test_provider_failure_marks_the_whole_batch_failed(
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    chunk_repository: FakeDocumentChunkRepository,
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
    provider: FakeEmbeddingProvider,
) -> None:
    document, chunks, user = _setup_processed_document(
        document_repository, engagement_repository, chunk_repository, embedding_repository,
        num_chunks=3,
    )
    provider.error = EmbeddingProviderUnavailableError("down")
    service = EmbeddingGenerationService(
        document_repository, engagement_repository, chunk_repository, embedding_repository,
        provider, provider_name=PROVIDER_NAME, model=MODEL, model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, max_batch_size=100, stale_after_seconds=300,
    )

    summary = await service.generate_for_document(document.id, user)

    assert summary.failed == 3
    assert summary.newly_completed == 0
    failed_rows = [r for r in embedding_repository.rows.values() if r.status == "FAILED"]
    assert len(failed_rows) == 3
    assert all(r.error_message == "Embedding provider unavailable" for r in failed_rows)


async def test_second_round_failure_leaves_first_round_completed(
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    chunk_repository: FakeDocumentChunkRepository,
    embedding_repository: FakeDocumentChunkEmbeddingRepository,
) -> None:
    document, chunks, user = _setup_processed_document(
        document_repository, engagement_repository, chunk_repository, embedding_repository,
        num_chunks=4,
    )

    class FlakyProvider(EmbeddingProvider):
        def __init__(self) -> None:
            self.call_count = 0

        async def embed_texts(self, texts: Sequence[str]) -> Sequence[EmbeddingResult]:
            self.call_count += 1
            if self.call_count == 2:
                raise EmbeddingProviderUnavailableError("round 2 failed")
            return [
                EmbeddingResult(text=t, vector=[0.1] * DIMENSION, dimension=DIMENSION)
                for t in texts
            ]

    flaky_provider = FlakyProvider()
    service = EmbeddingGenerationService(
        document_repository, engagement_repository, chunk_repository, embedding_repository,
        flaky_provider, provider_name=PROVIDER_NAME, model=MODEL, model_version=MODEL_VERSION,
        embedding_dimension=DIMENSION, max_batch_size=2, stale_after_seconds=300,
    )

    summary = await service.generate_for_document(document.id, user)

    assert summary.newly_completed == 2  # first round of 2
    assert summary.failed == 2  # second round of 2
    completed = [r for r in embedding_repository.rows.values() if r.status == "COMPLETED"]
    failed = [r for r in embedding_repository.rows.values() if r.status == "FAILED"]
    assert len(completed) == 2
    assert len(failed) == 2
