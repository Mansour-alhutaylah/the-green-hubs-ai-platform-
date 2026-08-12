"""Unit tests for ``DocumentProcessingService`` -- business logic exercised
against in-memory fake repositories, fake storage, and a fake unit of
work. The real, unmodified text extractor and chunker are exercised
against real (in-memory-generated) PDF bytes -- no database, no network,
no ``integration`` mark.
"""

import tempfile
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import pytest

from app.core.exceptions import (
    AppError,
    AuthorizationError,
    InvalidStateTransitionError,
    NotFoundError,
    PersistenceError,
    ValidationError,
)
from app.domain.entities.document import Document
from app.domain.entities.document_chunk import DocumentChunk
from app.domain.entities.engagement import Engagement
from app.domain.entities.extracted_text import ExtractedText
from app.domain.entities.user import User
from app.domain.processing_unit_of_work import IProcessingUnitOfWork
from app.domain.repositories.document import IDocumentRepository
from app.domain.repositories.document_chunk import IDocumentChunkRepository
from app.domain.repositories.engagement import IEngagementRepository
from app.domain.repositories.extracted_text import IExtractedTextRepository
from app.domain.storage.document_storage import (
    IDocumentStorage,
    StorageConfigurationError,
    StorageObjectNotFoundError,
    StorageUnavailableError,
)
from app.infrastructure.documents.text_extractor import TextExtractionError
from app.services.document_processing import DocumentProcessingService, _extract_text_from_bytes


def _make_pdf_bytes(text: str = "Test document content") -> bytes:
    """Build real, valid, extractable PDF bytes in memory. Uses
    ``insert_textbox`` (not ``insert_text``) so arbitrarily long text wraps
    within the page instead of being silently clipped at the page edge."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    rect = pymupdf.Rect(36, 36, page.rect.width - 36, page.rect.height - 36)
    page.insert_textbox(rect, text, fontsize=8)
    content = doc.tobytes()
    doc.close()
    return content


class FakeDocumentRepository(IDocumentRepository):
    """In-memory ``IDocumentRepository`` that models the real tenant join.

    ``documents`` has no ``organization_id`` column, so the real
    repository resolves ownership through
    ``documents.engagement_id -> engagements.organization_id``.
    ``engagement_organizations`` below is that join: every tenant-scoped
    method resolves the caller's scope through it and returns nothing for
    a foreign document, exactly as the SQL does. A fake that ignored
    ``organization_id`` would let these tests pass while the service was
    wide open.
    """

    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, Document] = {}
        self.engagement_organizations: dict[uuid.UUID, uuid.UUID | None] = {}
        self.begin_processing_error: Exception | None = None
        self.complete_processing_error: Exception | None = None
        self.status_history: list[tuple[uuid.UUID, str]] = []

    def seed(self, document: Document) -> None:
        self.rows[document.id] = document

    def seed_ownership(
        self, engagement_id: uuid.UUID, organization_id: uuid.UUID | None
    ) -> None:
        self.engagement_organizations[engagement_id] = organization_id

    def _owned(self, document_id: uuid.UUID, organization_id: uuid.UUID) -> Document | None:
        document = self.rows.get(document_id)
        if document is None:
            return None
        owner = self.engagement_organizations.get(document.engagement_id)
        if owner is None or owner != organization_id:
            return None
        return document



    async def create(self, entity: Document) -> Document:
        raise NotImplementedError

    async def update(self, entity: Document) -> Document:
        raise NotImplementedError

    async def delete(self, entity: Document) -> None:
        raise NotImplementedError

    async def get_for_organization(
        self, document_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Document | None:
        return self._owned(document_id, organization_id)

    async def get_by_engagement(
        self, engagement_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Sequence[Document]:
        if self.engagement_organizations.get(engagement_id) != organization_id:
            return []
        return [d for d in self.rows.values() if d.engagement_id == engagement_id]

    async def update_status(
        self, document_id: uuid.UUID, status: str, *, organization_id: uuid.UUID
    ) -> Document:
        self.status_history.append((document_id, status))
        existing = self._owned(document_id, organization_id)
        if existing is None:
            raise NotFoundError(f"Document {document_id} not found")
        updated = replace(existing, processing_status=status)
        self.rows[document_id] = updated
        return updated

    async def begin_processing(
        self, document_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Document:
        if self.begin_processing_error is not None:
            raise self.begin_processing_error
        existing = self._owned(document_id, organization_id)
        if existing is None:
            raise NotFoundError(f"Document {document_id} not found")
        messages = {
            "PROCESSING": "Document is already being processed.",
            "PROCESSED": "Document has already been processed.",
            "FAILED": "Failed documents cannot be reprocessed in this sprint.",
        }
        if existing.processing_status != "PENDING":
            raise InvalidStateTransitionError(
                messages.get(
                    existing.processing_status,
                    f"Document is not PENDING (state: {existing.processing_status}).",
                )
            )
        updated = replace(existing, processing_status="PROCESSING")
        self.rows[document_id] = updated
        return updated

    async def complete_processing(
        self, document_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Document:
        if self.complete_processing_error is not None:
            raise self.complete_processing_error
        existing = self._owned(document_id, organization_id)
        if existing is None:
            raise NotFoundError(f"Document {document_id} not found")
        updated = replace(existing, processing_status="PROCESSED")
        self.rows[document_id] = updated
        return updated

    async def get_read_model_for_organization(self, document_id: uuid.UUID, *, organization_id: uuid.UUID):
        raise NotImplementedError

    async def list_read_models_for_organization(self, *, organization_id: uuid.UUID, engagement_id=None, processing_status=None, limit: int, offset: int):
        raise NotImplementedError

    async def count_for_organization(self, *, organization_id: uuid.UUID, engagement_id=None, processing_status=None) -> int:
        raise NotImplementedError


class FakeEngagementRepository(IEngagementRepository):
    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, Engagement] = {}

    def seed(self, engagement: Engagement) -> None:
        assert engagement.id is not None
        self._rows[engagement.id] = engagement


    async def list(
        self, *, limit: int = 100, offset: int = 0, organization_id: uuid.UUID | None = None
    ) -> Sequence[Engagement]:
        rows = list(self._rows.values())
        if organization_id is not None:
            rows = [r for r in rows if r.organization_id == organization_id]
        return rows[offset : offset + limit]

    async def count(self, *, organization_id: uuid.UUID) -> int:
        return len([r for r in self._rows.values() if r.organization_id == organization_id])

    async def get_for_organization(
        self, entity_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Engagement | None:
        row = self._rows.get(entity_id)
        if row is not None and row.organization_id == organization_id:
            return row
        return None

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


class FakeExtractedTextRepository(IExtractedTextRepository):
    def __init__(self) -> None:
        self.rows: list[ExtractedText] = []
        self.create_error: Exception | None = None

    async def create(self, entity: ExtractedText) -> ExtractedText:
        if self.create_error is not None:
            raise self.create_error
        created = replace(entity, id=uuid.uuid4())
        self.rows.append(created)
        return created

    async def get_by_document(
        self, document_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> ExtractedText | None:
        for row in self.rows:
            if row.document_id == document_id:
                return row
        return None

    async def delete(self, entity: ExtractedText) -> None:
        self.rows = [r for r in self.rows if r.id != entity.id]


class FakeDocumentChunkRepository(IDocumentChunkRepository):
    def __init__(self) -> None:
        self.rows: list[DocumentChunk] = []
        self.create_many_error: Exception | None = None

    async def create_many(self, entities: Sequence[DocumentChunk]) -> Sequence[DocumentChunk]:
        if self.create_many_error is not None:
            raise self.create_many_error
        created = [replace(e, id=uuid.uuid4()) for e in entities]
        self.rows.extend(created)
        return created

    async def get_by_document(
        self, document_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Sequence[DocumentChunk]:
        return [r for r in self.rows if r.document_id == document_id]

    async def delete(self, entity: DocumentChunk) -> None:
        self.rows = [r for r in self.rows if r.id != entity.id]


class FakeDocumentStorage(IDocumentStorage):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.get_error: Exception | None = None
        self.put_calls: list[tuple[str, bytes, str]] = []
        self.delete_calls: list[str] = []

    def seed(self, object_key: str, content: bytes) -> None:
        self.objects[object_key] = content

    async def put(self, object_key: str, content: bytes, content_type: str) -> None:
        self.put_calls.append((object_key, content, content_type))
        self.objects[object_key] = content

    async def get(self, object_key: str) -> bytes:
        if self.get_error is not None:
            raise self.get_error
        if object_key not in self.objects:
            raise StorageObjectNotFoundError(object_key)
        return self.objects[object_key]

    async def delete(self, object_key: str) -> None:
        self.delete_calls.append(object_key)
        self.objects.pop(object_key, None)


class FakeUnitOfWork(IProcessingUnitOfWork):
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.commit_error: Exception | None = None

    async def commit(self) -> None:
        if self.commit_error is not None:
            raise self.commit_error
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


@pytest.fixture
def document_repository() -> FakeDocumentRepository:
    return FakeDocumentRepository()


@pytest.fixture
def engagement_repository() -> FakeEngagementRepository:
    return FakeEngagementRepository()


@pytest.fixture
def extracted_text_repository() -> FakeExtractedTextRepository:
    return FakeExtractedTextRepository()


@pytest.fixture
def chunk_repository() -> FakeDocumentChunkRepository:
    return FakeDocumentChunkRepository()


@pytest.fixture
def storage() -> FakeDocumentStorage:
    return FakeDocumentStorage()


@pytest.fixture
def unit_of_work() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def service(
    document_repository: FakeDocumentRepository,
    extracted_text_repository: FakeExtractedTextRepository,
    chunk_repository: FakeDocumentChunkRepository,
    storage: FakeDocumentStorage,
    unit_of_work: FakeUnitOfWork,
) -> DocumentProcessingService:
    # No engagement repository: MVP Slice 3 moved the ownership chain
    # into IDocumentRepository's own tenant-scoped queries.
    return DocumentProcessingService(
        document_repository,
        extracted_text_repository,
        chunk_repository,
        storage,
        unit_of_work,
    )


def _engagement(organization_id: uuid.UUID | None) -> Engagement:
    return Engagement(
        id=uuid.uuid4(),
        organization_id=organization_id,
        title="Test Engagement",
        status="planning",
        created_at=datetime.now(timezone.utc),
    )


def _user(organization_id: uuid.UUID | None) -> User:
    return User(
        id=uuid.uuid4(),
        organization_id=organization_id,
        full_name="Test User",
        email="test@example.com",
        role="admin",
        created_at=datetime.now(timezone.utc),
    )


def _document(engagement_id: uuid.UUID, storage_path: str, status: str = "PENDING") -> Document:
    now = datetime.now(timezone.utc)
    return Document(
        id=uuid.uuid4(),
        filename="report.pdf",
        storage_path=storage_path,
        processing_status=status,
        engagement_id=engagement_id,
        created_at=now,
        updated_at=now,
    )


def _setup_ready_document(
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
    *,
    pdf_text: str = "Test document content",
    status: str = "PENDING",
) -> tuple[Document, Engagement, User]:
    organization_id = uuid.uuid4()
    engagement = _engagement(organization_id)
    engagement_repository.seed(engagement)
    assert engagement.id is not None
    document = _document(engagement.id, f"organizations/{organization_id}/doc.pdf", status=status)
    document_repository.seed(document)
    document_repository.seed_ownership(engagement.id, organization_id)
    storage.seed(document.storage_path, _make_pdf_bytes(pdf_text))
    user = _user(organization_id)
    return document, engagement, user


# ---------------------------------------------------------------------------
# Successful processing
# ---------------------------------------------------------------------------


async def test_successful_full_processing_flow(
    service: DocumentProcessingService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
    extracted_text_repository: FakeExtractedTextRepository,
    chunk_repository: FakeDocumentChunkRepository,
    unit_of_work: FakeUnitOfWork,
) -> None:
    # A long, repeated text forces multiple chunks at the default chunk_size.
    long_text = "This is a sustainability report sentence. " * 40
    document, _engagement, user = _setup_ready_document(
        document_repository, engagement_repository, storage, pdf_text=long_text
    )

    result = await service.process(document.id, user)

    assert result.processing_status == "PROCESSED"
    assert document_repository.status_history == [] or all(
        status != "FAILED" for _doc_id, status in document_repository.status_history
    )
    assert len(extracted_text_repository.rows) == 1
    assert extracted_text_repository.rows[0].document_id == document.id
    assert len(chunk_repository.rows) >= 1
    indexes = sorted(c.chunk_index for c in chunk_repository.rows)
    assert indexes == list(range(len(indexes)))  # deterministic, sequential, starting at 0
    assert unit_of_work.committed is True
    assert unit_of_work.rolled_back is False


async def test_deterministic_sequential_chunk_indexes(
    service: DocumentProcessingService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
    chunk_repository: FakeDocumentChunkRepository,
) -> None:
    long_text = "Emissions data point number recorded here. " * 60
    document, _engagement, user = _setup_ready_document(
        document_repository, engagement_repository, storage, pdf_text=long_text
    )

    await service.process(document.id, user)

    chunks_for_doc = sorted(chunk_repository.rows, key=lambda c: c.chunk_index)
    assert len(chunks_for_doc) > 1
    assert [c.chunk_index for c in chunks_for_doc] == list(range(len(chunks_for_doc)))
    for chunk in chunks_for_doc:
        assert chunk.document_id == document.id


async def test_persisted_chunk_offsets_map_to_normalized_text(
    service: DocumentProcessingService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
    extracted_text_repository: FakeExtractedTextRepository,
    chunk_repository: FakeDocumentChunkRepository,
) -> None:
    long_text = "Emissions data point number recorded here. " * 60
    document, _engagement, user = _setup_ready_document(
        document_repository, engagement_repository, storage, pdf_text=long_text
    )

    await service.process(document.id, user)

    normalized_text = extracted_text_repository.rows[0].extracted_content
    assert normalized_text is not None
    chunks_for_doc = sorted(chunk_repository.rows, key=lambda c: c.chunk_index)
    assert len(chunks_for_doc) > 1
    for chunk in chunks_for_doc:
        assert chunk.char_start >= 0
        assert chunk.char_end > chunk.char_start
        assert normalized_text[chunk.char_start : chunk.char_end] == chunk.content
    starts = [c.char_start for c in chunks_for_doc]
    assert starts == sorted(starts)  # offsets increase consistently with chunk order
    assert len(starts) == len(set(starts))  # no duplicate starting offsets


# ---------------------------------------------------------------------------
# Not found / authorization
# ---------------------------------------------------------------------------


async def test_missing_document_raises_not_found(
    service: DocumentProcessingService,
) -> None:
    user = _user(uuid.uuid4())
    with pytest.raises(NotFoundError):
        await service.process(uuid.uuid4(), user)


async def test_document_whose_engagement_has_no_owner_raises_not_found(
    service: DocumentProcessingService, document_repository: FakeDocumentRepository
) -> None:
    """Fail closed: an engagement with no organization is owned by nobody,
    so it can never match a caller's scope."""

    document = _document(uuid.uuid4(), "organizations/x/doc.pdf")
    document_repository.seed(document)
    document_repository.seed_ownership(document.engagement_id, None)
    user = _user(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await service.process(document.id, user)


async def test_user_without_organization_raises_authorization_error(
    service: DocumentProcessingService,
    document_repository: FakeDocumentRepository,
) -> None:
    """No organization means no tenant scope at all -- 403, and the
    rejection happens before any document is looked up."""

    organization_id = uuid.uuid4()
    engagement = _engagement(organization_id)
    assert engagement.id is not None
    document = _document(engagement.id, "organizations/x/doc.pdf")
    document_repository.seed(document)
    document_repository.seed_ownership(engagement.id, organization_id)
    user = _user(None)

    with pytest.raises(AuthorizationError):
        await service.process(document.id, user)


async def test_organization_mismatch_raises_not_found_not_authorization_error(
    service: DocumentProcessingService,
    document_repository: FakeDocumentRepository,
) -> None:
    """MVP Slice 3: a valid Document UUID owned by another organization is
    indistinguishable from one that does not exist.

    Before this slice the mismatch raised ``AuthorizationError`` (403)
    while an unknown id raised ``NotFoundError`` (404), so an attacker
    holding a real UUID could tell the two apart -- a cross-tenant
    existence oracle. Both are 404 now.
    """

    owner_organization_id = uuid.uuid4()
    engagement = _engagement(owner_organization_id)
    assert engagement.id is not None
    document = _document(engagement.id, "organizations/x/doc.pdf")
    document_repository.seed(document)
    document_repository.seed_ownership(engagement.id, owner_organization_id)
    attacker = _user(uuid.uuid4())  # a different organization

    with pytest.raises(NotFoundError):
        await service.process(document.id, attacker)


async def test_cross_tenant_process_never_mutates_the_foreign_document(
    service: DocumentProcessingService,
    document_repository: FakeDocumentRepository,
) -> None:
    """The rejected request must leave no trace on the victim's row --
    not even the FAILED status the error path would otherwise write."""

    owner_organization_id = uuid.uuid4()
    engagement = _engagement(owner_organization_id)
    assert engagement.id is not None
    document = _document(engagement.id, "organizations/x/doc.pdf")
    document_repository.seed(document)
    document_repository.seed_ownership(engagement.id, owner_organization_id)
    attacker = _user(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await service.process(document.id, attacker)

    assert document_repository.rows[document.id].processing_status == "PENDING"
    assert document_repository.status_history == []


# ---------------------------------------------------------------------------
# State transitions -- 409, exact messages
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "state,expected_message",
    [
        ("PROCESSING", "Document is already being processed."),
        ("PROCESSED", "Document has already been processed."),
        ("FAILED", "Failed documents cannot be reprocessed in this sprint."),
    ],
)
async def test_non_pending_states_rejected_with_409_and_exact_message(
    service: DocumentProcessingService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
    state: str,
    expected_message: str,
) -> None:
    document, _engagement, user = _setup_ready_document(
        document_repository, engagement_repository, storage, status=state
    )

    with pytest.raises(InvalidStateTransitionError) as exc_info:
        await service.process(document.id, user)

    assert exc_info.value.message == expected_message
    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# Storage failures
# ---------------------------------------------------------------------------


async def test_storage_object_missing_maps_to_not_found_and_marks_failed(
    service: DocumentProcessingService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
) -> None:
    organization_id = uuid.uuid4()
    engagement = _engagement(organization_id)
    engagement_repository.seed(engagement)
    assert engagement.id is not None
    document = _document(engagement.id, "organizations/x/never-stored.pdf")
    document_repository.seed(document)
    document_repository.seed_ownership(engagement.id, organization_id)
    user = _user(organization_id)
    # Deliberately never seed storage.objects -- the object doesn't exist.

    with pytest.raises(NotFoundError):
        await service.process(document.id, user)

    assert document_repository.status_history[-1] == (document.id, "FAILED")


async def test_storage_unavailable_maps_to_persistence_error(
    service: DocumentProcessingService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
) -> None:
    document, _engagement, user = _setup_ready_document(
        document_repository, engagement_repository, storage
    )
    storage.get_error = StorageUnavailableError("network down")

    with pytest.raises(PersistenceError):
        await service.process(document.id, user)

    assert document_repository.status_history[-1] == (document.id, "FAILED")


async def test_storage_configuration_failure_maps_to_persistence_error(
    service: DocumentProcessingService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
) -> None:
    document, _engagement, user = _setup_ready_document(
        document_repository, engagement_repository, storage
    )
    storage.get_error = StorageConfigurationError("bad credentials")

    with pytest.raises(PersistenceError):
        await service.process(document.id, user)

    assert document_repository.status_history[-1] == (document.id, "FAILED")


# ---------------------------------------------------------------------------
# Extraction / content failures
# ---------------------------------------------------------------------------


async def test_extraction_failure_maps_to_validation_error_and_marks_failed(
    service: DocumentProcessingService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
) -> None:
    organization_id = uuid.uuid4()
    engagement = _engagement(organization_id)
    engagement_repository.seed(engagement)
    assert engagement.id is not None
    document = _document(engagement.id, "organizations/x/corrupt.pdf")
    document_repository.seed(document)
    document_repository.seed_ownership(engagement.id, organization_id)
    storage.seed(document.storage_path, b"this is not a real pdf file")
    user = _user(organization_id)

    with pytest.raises(ValidationError):
        await service.process(document.id, user)

    assert document_repository.status_history[-1] == (document.id, "FAILED")


async def test_empty_extracted_text_raises_validation_error(
    service: DocumentProcessingService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
) -> None:
    # A real, valid PDF page with no text on it -- extraction succeeds but
    # yields nothing.
    document, _engagement, user = _setup_ready_document(
        document_repository, engagement_repository, storage, pdf_text=""
    )

    with pytest.raises(ValidationError):
        await service.process(document.id, user)

    assert document_repository.status_history[-1] == (document.id, "FAILED")


# ---------------------------------------------------------------------------
# Persistence failures and rollback
# ---------------------------------------------------------------------------


async def test_extracted_text_insert_failure_rolls_back_and_marks_failed(
    service: DocumentProcessingService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
    extracted_text_repository: FakeExtractedTextRepository,
    unit_of_work: FakeUnitOfWork,
) -> None:
    document, _engagement, user = _setup_ready_document(
        document_repository, engagement_repository, storage
    )
    extracted_text_repository.create_error = PersistenceError("db exploded")

    with pytest.raises(PersistenceError):
        await service.process(document.id, user)

    assert unit_of_work.rolled_back is True
    assert unit_of_work.committed is False
    assert document_repository.status_history[-1] == (document.id, "FAILED")


async def test_bulk_chunk_insert_failure_rolls_back_and_marks_failed(
    service: DocumentProcessingService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
    chunk_repository: FakeDocumentChunkRepository,
    unit_of_work: FakeUnitOfWork,
) -> None:
    document, _engagement, user = _setup_ready_document(
        document_repository, engagement_repository, storage
    )
    chunk_repository.create_many_error = PersistenceError("db exploded")

    with pytest.raises(PersistenceError):
        await service.process(document.id, user)

    assert unit_of_work.rolled_back is True
    assert unit_of_work.committed is False
    assert document_repository.status_history[-1] == (document.id, "FAILED")


async def test_failed_status_persisted_even_when_nothing_was_written_yet(
    service: DocumentProcessingService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
) -> None:
    """Storage retrieval fails before any transactional write -- FAILED
    must still be persisted, since the Document is already PROCESSING."""
    document, _engagement, user = _setup_ready_document(
        document_repository, engagement_repository, storage
    )
    storage.get_error = StorageUnavailableError("down")

    with pytest.raises(AppError):
        await service.process(document.id, user)

    assert document_repository.rows[document.id].processing_status == "FAILED"


async def test_final_commit_failure_still_marks_failed(
    service: DocumentProcessingService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
    unit_of_work: FakeUnitOfWork,
) -> None:
    document, _engagement, user = _setup_ready_document(
        document_repository, engagement_repository, storage
    )
    unit_of_work.commit_error = PersistenceError("commit failed")

    with pytest.raises(PersistenceError):
        await service.process(document.id, user)

    assert unit_of_work.rolled_back is True
    assert document_repository.status_history[-1] == (document.id, "FAILED")


async def test_failure_to_persist_failed_status_does_not_mask_original_error(
    service: DocumentProcessingService,
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
) -> None:
    document, _engagement, user = _setup_ready_document(
        document_repository, engagement_repository, storage
    )
    storage.get_error = StorageUnavailableError("down")
    document_repository.complete_processing_error = RuntimeError("unrelated")
    # Force update_status (used for the FAILED compensation) to also fail,
    # by removing the row between begin_processing and the failure handler
    # -- simulate via a second, dedicated repository error hook instead:
    original_update_status = document_repository.update_status

    async def failing_update_status(document_id: uuid.UUID, status: str) -> Document:
        if status == "FAILED":
            raise PersistenceError("cannot persist FAILED either")
        return await original_update_status(document_id, status)

    document_repository.update_status = failing_update_status  # type: ignore[method-assign]

    with pytest.raises(PersistenceError) as exc_info:
        await service.process(document.id, user)

    # The ORIGINAL error (storage unavailable) is what the caller sees, not
    # a generic error about the FAILED-status update itself.
    assert exc_info.value.message == "Unable to retrieve the stored document"


# ---------------------------------------------------------------------------
# Temporary-file handling
# ---------------------------------------------------------------------------


async def test_temporary_file_removed_after_successful_extraction() -> None:
    pdf_bytes = _make_pdf_bytes("Temp file cleanup test")
    before = set(Path(tempfile.gettempdir()).glob("tmp*.pdf"))

    result = await _extract_text_from_bytes(pdf_bytes)

    after = set(Path(tempfile.gettempdir()).glob("tmp*.pdf"))
    assert "Temp file cleanup test" in result
    assert after <= before  # no new leftover .pdf temp files


async def test_temporary_file_cleanup_never_masks_the_original_extraction_error() -> None:
    """A failed-to-open PDF must surface as ``TextExtractionError`` --
    never as an unrelated OS error from the ``finally``-block cleanup
    attempt (e.g. a parsing library holding its file handle open a moment
    longer than the call that raised, which some OSes refuse to unlink
    around)."""
    with pytest.raises(TextExtractionError):
        await _extract_text_from_bytes(b"not a real pdf")


async def test_temporary_filename_never_matches_original_document_filename() -> None:
    pdf_bytes = _make_pdf_bytes("Filename isolation test")
    captured_paths: list[str] = []

    import app.services.document_processing as processing_module

    original_extract_text = processing_module.extract_text

    async def spying_extract_text(path: Path) -> str:
        captured_paths.append(str(path))
        return await original_extract_text(path)

    processing_module.extract_text = spying_extract_text  # type: ignore[assignment]
    try:
        await _extract_text_from_bytes(pdf_bytes)
    finally:
        processing_module.extract_text = original_extract_text  # type: ignore[assignment]

    assert len(captured_paths) == 1
    assert "report" not in captured_paths[0]
    assert "sustainability" not in captured_paths[0]
