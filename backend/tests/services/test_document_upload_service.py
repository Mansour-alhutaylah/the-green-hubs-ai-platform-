"""Unit tests for ``DocumentUploadService`` -- business logic exercised
against in-memory fake repositories and fake storage. No database, no
HTTP, no network, no ``integration`` mark.
"""

import uuid
from datetime import datetime, timezone
from typing import Sequence

import pytest

from app.core.exceptions import (
    AuthorizationError,
    NotFoundError,
    PersistenceError,
    ValidationError,
)
from app.domain.entities.document import Document
from app.domain.entities.engagement import Engagement
from app.domain.entities.user import User
from app.domain.repositories.document import IDocumentRepository
from app.domain.repositories.engagement import IEngagementRepository
from app.domain.storage.document_storage import IDocumentStorage, StorageError
from app.services.document_upload import DocumentUploadInput, DocumentUploadService

PDF_BYTES = b"%PDF-1.4\n%Fake PDF content for tests\n%%EOF"
MAX_SIZE = 1024 * 1024


class FakeDocumentRepository(IDocumentRepository):
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, Document] = {}
        self.create_error: Exception | None = None



    async def create(self, entity: Document) -> Document:
        if self.create_error is not None:
            raise self.create_error
        self.rows[entity.id] = entity
        return entity

    async def update(self, entity: Document) -> Document:
        raise NotImplementedError

    async def delete(self, entity: Document) -> None:
        raise NotImplementedError

    async def get_for_organization(
        self, document_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Document | None:
        raise NotImplementedError

    async def get_by_engagement(
        self, engagement_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Sequence[Document]:
        return [d for d in self.rows.values() if d.engagement_id == engagement_id]

    async def update_status(
        self, document_id: uuid.UUID, status: str, *, organization_id: uuid.UUID
    ) -> Document:
        raise NotImplementedError

    async def begin_processing(
        self, document_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Document:
        raise NotImplementedError

    async def complete_processing(
        self, document_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Document:
        raise NotImplementedError

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


class FakeDocumentStorage(IDocumentStorage):
    def __init__(self) -> None:
        self.put_calls: list[tuple[str, bytes, str]] = []
        self.delete_calls: list[str] = []
        self.put_error: Exception | None = None
        self.delete_error: Exception | None = None

    async def put(self, object_key: str, content: bytes, content_type: str) -> None:
        self.put_calls.append((object_key, content, content_type))
        if self.put_error is not None:
            raise self.put_error

    async def get(self, object_key: str) -> bytes:
        raise NotImplementedError

    async def delete(self, object_key: str) -> None:
        self.delete_calls.append(object_key)
        if self.delete_error is not None:
            raise self.delete_error


@pytest.fixture
def document_repository() -> FakeDocumentRepository:
    return FakeDocumentRepository()


@pytest.fixture
def engagement_repository() -> FakeEngagementRepository:
    return FakeEngagementRepository()


@pytest.fixture
def storage() -> FakeDocumentStorage:
    return FakeDocumentStorage()


@pytest.fixture
def service(
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
) -> DocumentUploadService:
    return DocumentUploadService(
        document_repository, engagement_repository, storage, max_upload_size_bytes=MAX_SIZE
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


def _upload_input(engagement_id: uuid.UUID, **overrides: object) -> DocumentUploadInput:
    defaults: dict = {
        "engagement_id": engagement_id,
        "original_filename": "report.pdf",
        "declared_content_type": "application/pdf",
        "content": PDF_BYTES,
    }
    defaults.update(overrides)
    return DocumentUploadInput(**defaults)


async def test_successful_upload_orchestration(
    service: DocumentUploadService,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
    document_repository: FakeDocumentRepository,
) -> None:
    organization_id = uuid.uuid4()
    engagement = _engagement(organization_id)
    engagement_repository.seed(engagement)
    user = _user(organization_id)

    document = await service.upload(_upload_input(engagement.id), current_user=user)  # type: ignore[arg-type]

    assert document.engagement_id == engagement.id
    assert document.processing_status == "PENDING"
    assert document.filename == "report.pdf"
    assert len(storage.put_calls) == 1
    key, content, content_type = storage.put_calls[0]
    assert content == PDF_BYTES
    assert content_type == "application/pdf"
    assert str(engagement.organization_id) in key
    assert str(engagement.id) in key
    assert key.endswith(".pdf")
    assert document.id in document_repository.rows


async def test_missing_engagement_raises_not_found(service: DocumentUploadService) -> None:
    user = _user(uuid.uuid4())
    with pytest.raises(NotFoundError):
        await service.upload(_upload_input(uuid.uuid4()), current_user=user)


async def test_user_without_organization_raises_authorization_error(
    service: DocumentUploadService, engagement_repository: FakeEngagementRepository
) -> None:
    engagement = _engagement(uuid.uuid4())
    engagement_repository.seed(engagement)
    user = _user(None)

    with pytest.raises(AuthorizationError):
        await service.upload(_upload_input(engagement.id), current_user=user)  # type: ignore[arg-type]


async def test_engagement_without_organization_raises_not_found(
    service: DocumentUploadService, engagement_repository: FakeEngagementRepository
) -> None:
    """Fail closed: an Engagement owned by nobody matches no tenant scope,
    so it reads as not found rather than as a distinct 403."""

    engagement = _engagement(None)
    engagement_repository.seed(engagement)
    user = _user(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await service.upload(_upload_input(engagement.id), current_user=user)  # type: ignore[arg-type]


async def test_organization_mismatch_raises_not_found_not_authorization_error(
    service: DocumentUploadService,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
    document_repository: FakeDocumentRepository,
) -> None:
    """MVP Slice 3: a real Engagement UUID from another organization must
    be indistinguishable from one that does not exist.

    Previously this raised ``AuthorizationError`` (403) while
    ``test_missing_engagement_raises_not_found`` above raised 404, so the
    pair of responses told a caller which foreign Engagement UUIDs were
    real. Both are 404 now, and nothing is written on the way out.
    """

    engagement = _engagement(uuid.uuid4())
    engagement_repository.seed(engagement)
    attacker = _user(uuid.uuid4())  # a different organization

    with pytest.raises(NotFoundError):
        await service.upload(_upload_input(engagement.id), current_user=attacker)  # type: ignore[arg-type]

    assert storage.put_calls == []
    assert document_repository.rows == {}


async def test_invalid_filename_raises_validation_error(
    service: DocumentUploadService, engagement_repository: FakeEngagementRepository
) -> None:
    organization_id = uuid.uuid4()
    engagement = _engagement(organization_id)
    engagement_repository.seed(engagement)
    user = _user(organization_id)

    with pytest.raises(ValidationError):
        await service.upload(
            _upload_input(engagement.id, original_filename="report.txt"),  # type: ignore[arg-type]
            current_user=user,
        )


async def test_blank_filename_raises_validation_error(
    service: DocumentUploadService, engagement_repository: FakeEngagementRepository
) -> None:
    organization_id = uuid.uuid4()
    engagement = _engagement(organization_id)
    engagement_repository.seed(engagement)
    user = _user(organization_id)

    with pytest.raises(ValidationError):
        await service.upload(
            _upload_input(engagement.id, original_filename="   "),  # type: ignore[arg-type]
            current_user=user,
        )


async def test_unsupported_content_type_raises_validation_error(
    service: DocumentUploadService, engagement_repository: FakeEngagementRepository
) -> None:
    organization_id = uuid.uuid4()
    engagement = _engagement(organization_id)
    engagement_repository.seed(engagement)
    user = _user(organization_id)

    with pytest.raises(ValidationError):
        await service.upload(
            _upload_input(engagement.id, declared_content_type="text/plain"),  # type: ignore[arg-type]
            current_user=user,
        )


async def test_invalid_pdf_signature_raises_validation_error(
    service: DocumentUploadService, engagement_repository: FakeEngagementRepository
) -> None:
    organization_id = uuid.uuid4()
    engagement = _engagement(organization_id)
    engagement_repository.seed(engagement)
    user = _user(organization_id)

    with pytest.raises(ValidationError):
        await service.upload(
            _upload_input(engagement.id, content=b"this is not a pdf"),  # type: ignore[arg-type]
            current_user=user,
        )


async def test_zero_byte_file_raises_validation_error(
    service: DocumentUploadService, engagement_repository: FakeEngagementRepository
) -> None:
    organization_id = uuid.uuid4()
    engagement = _engagement(organization_id)
    engagement_repository.seed(engagement)
    user = _user(organization_id)

    with pytest.raises(ValidationError):
        await service.upload(
            _upload_input(engagement.id, content=b""),  # type: ignore[arg-type]
            current_user=user,
        )


async def test_oversized_file_raises_validation_error(
    document_repository: FakeDocumentRepository,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
) -> None:
    tiny_limit_service = DocumentUploadService(
        document_repository, engagement_repository, storage, max_upload_size_bytes=10
    )
    organization_id = uuid.uuid4()
    engagement = _engagement(organization_id)
    engagement_repository.seed(engagement)
    user = _user(organization_id)

    with pytest.raises(ValidationError):
        await tiny_limit_service.upload(_upload_input(engagement.id), current_user=user)  # type: ignore[arg-type]


async def test_storage_failure_raises_persistence_error_and_creates_no_row(
    service: DocumentUploadService,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
    document_repository: FakeDocumentRepository,
) -> None:
    organization_id = uuid.uuid4()
    engagement = _engagement(organization_id)
    engagement_repository.seed(engagement)
    user = _user(organization_id)
    storage.put_error = StorageError("boom")

    with pytest.raises(PersistenceError):
        await service.upload(_upload_input(engagement.id), current_user=user)  # type: ignore[arg-type]

    assert document_repository.rows == {}


async def test_database_failure_after_storage_success_triggers_compensation(
    service: DocumentUploadService,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
    document_repository: FakeDocumentRepository,
) -> None:
    organization_id = uuid.uuid4()
    engagement = _engagement(organization_id)
    engagement_repository.seed(engagement)
    user = _user(organization_id)
    document_repository.create_error = PersistenceError("db exploded")

    with pytest.raises(PersistenceError):
        await service.upload(_upload_input(engagement.id), current_user=user)  # type: ignore[arg-type]

    assert len(storage.put_calls) == 1
    assert len(storage.delete_calls) == 1
    assert storage.delete_calls[0] == storage.put_calls[0][0]  # the exact key, nothing broader


async def test_compensation_delete_failure_still_raises_original_error(
    service: DocumentUploadService,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
    document_repository: FakeDocumentRepository,
) -> None:
    organization_id = uuid.uuid4()
    engagement = _engagement(organization_id)
    engagement_repository.seed(engagement)
    user = _user(organization_id)
    document_repository.create_error = PersistenceError("db exploded")
    storage.delete_error = StorageError("cleanup also failed")

    with pytest.raises(PersistenceError, match="db exploded"):
        await service.upload(_upload_input(engagement.id), current_user=user)  # type: ignore[arg-type]

    assert len(storage.delete_calls) == 1  # compensation was still attempted


async def test_concurrent_engagement_deletion_also_compensates(
    service: DocumentUploadService,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
    document_repository: FakeDocumentRepository,
) -> None:
    organization_id = uuid.uuid4()
    engagement = _engagement(organization_id)
    engagement_repository.seed(engagement)
    user = _user(organization_id)
    document_repository.create_error = NotFoundError("engagement vanished")

    with pytest.raises(NotFoundError):
        await service.upload(_upload_input(engagement.id), current_user=user)  # type: ignore[arg-type]

    assert len(storage.delete_calls) == 1


async def test_unique_object_key_generation(
    service: DocumentUploadService,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
) -> None:
    organization_id = uuid.uuid4()
    engagement = _engagement(organization_id)
    engagement_repository.seed(engagement)
    user = _user(organization_id)

    await service.upload(_upload_input(engagement.id), current_user=user)  # type: ignore[arg-type]
    await service.upload(_upload_input(engagement.id), current_user=user)  # type: ignore[arg-type]

    keys = [call[0] for call in storage.put_calls]
    assert len(keys) == 2
    assert keys[0] != keys[1]


async def test_object_key_never_contains_the_original_filename(
    service: DocumentUploadService,
    engagement_repository: FakeEngagementRepository,
    storage: FakeDocumentStorage,
) -> None:
    organization_id = uuid.uuid4()
    engagement = _engagement(organization_id)
    engagement_repository.seed(engagement)
    user = _user(organization_id)

    await service.upload(
        _upload_input(engagement.id, original_filename="super-secret-report-name.pdf"),  # type: ignore[arg-type]
        current_user=user,
    )

    key = storage.put_calls[0][0]
    assert "super-secret-report-name" not in key
