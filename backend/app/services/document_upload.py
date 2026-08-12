"""Document upload business logic / use case.

Deliberately framework-independent: no FastAPI import anywhere in this
module, no ``UploadFile``. ``DocumentUploadInput`` is the framework-free
boundary the API router converts an HTTP multipart request into before
ever calling this service -- every value on it is a plain Python type
(``UUID``, ``str``, ``bytes``), so this service is testable with ordinary
values and fakes, the same way ``EngagementService`` is testable without a
real HTTP request.

Constructed with ``IDocumentRepository``, ``IEngagementRepository``, and
``IDocumentStorage`` -- the domain abstractions, never a concrete
SQLAlchemy class or the Supabase SDK. Mirrors ``EngagementService``'s
precedent exactly: engagement/organization existence is checked here via
``IEngagementRepository`` directly (never ``EngagementService``), so
neither ``EngagementService`` nor ``OrganizationService`` needs any
redesign.

MVP Slice 3 (Organization Data Isolation): the Engagement is now loaded
through ``IEngagementRepository.get_for_organization``, so the caller's
organization is part of the SQL predicate that finds the row rather than
a Python comparison afterwards. The user-visible consequence is that an
Engagement belonging to another organization now returns
``NotFoundError`` (404), exactly like an Engagement that does not exist
-- previously it returned ``AuthorizationError`` (403), which let a
caller holding a valid Engagement UUID confirm it existed under some
other tenant. This aligns upload with the indistinguishable-not-found
convention already used by Organization/Engagement reads (Sprint 3.5.1),
embeddings (Sprint 3.6A) and analysis (Sprint 3.6B).

An Engagement whose ``organization_id`` is NULL likewise cannot match the
predicate, so the previous explicit "Engagement has no organization"
branch is now covered by the same fail-closed 404.

Ordering (see the Sprint 3.4 plan's "Upload order and compensation"
section): validate -> load Engagement tenant-scoped -> generate
id/object key -> store -> persist -> return.
There is no cross-system transaction between Postgres and Supabase
Storage -- if the database insert fails after the storage write already
succeeded, this service compensates by deleting the exact object it just
wrote, never anything broader. If that compensating delete itself fails,
it is logged (with the precise orphaned key) and swallowed -- the
original failure is what the caller sees, not a secondary cleanup error.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.exceptions import AuthorizationError, NotFoundError, PersistenceError, ValidationError
from app.domain.entities.document import Document
from app.domain.entities.user import User
from app.domain.repositories.document import IDocumentRepository
from app.domain.repositories.engagement import IEngagementRepository
from app.domain.storage.document_storage import IDocumentStorage, StorageError

logger = logging.getLogger(__name__)

_PDF_MAGIC_BYTES = b"%PDF-"
_PDF_CONTENT_TYPE = "application/pdf"
_MAX_FILENAME_LENGTH = 255


@dataclass
class DocumentUploadInput:
    """Framework-independent upload request -- everything the API router
    extracted from the HTTP multipart request, before this service is
    ever called."""

    engagement_id: UUID
    original_filename: str
    declared_content_type: str
    content: bytes


def _strip_control_characters(value: str) -> str:
    return "".join(ch for ch in value if ord(ch) >= 0x20 and ch != "\x7f")


def _sanitize_filename(original_filename: str) -> str:
    sanitized = _strip_control_characters(original_filename).strip()
    if not sanitized:
        raise ValidationError("filename must not be blank")
    return sanitized[:_MAX_FILENAME_LENGTH]


def _build_object_key(organization_id: UUID, engagement_id: UUID, document_id: UUID) -> str:
    return f"organizations/{organization_id}/engagements/{engagement_id}/documents/{document_id}.pdf"


class DocumentUploadService:
    def __init__(
        self,
        document_repository: IDocumentRepository,
        engagement_repository: IEngagementRepository,
        storage: IDocumentStorage,
        *,
        max_upload_size_bytes: int,
    ) -> None:
        self._document_repository = document_repository
        self._engagement_repository = engagement_repository
        self._storage = storage
        self._max_upload_size_bytes = max_upload_size_bytes

    async def upload(self, request: DocumentUploadInput, *, current_user: User) -> Document:
        sanitized_filename = _sanitize_filename(request.original_filename)
        self._validate_pdf(request)

        # Fail closed before any lookup: a profile with no organization
        # has no tenant scope, so there is no engagement it may upload to.
        organization_id = current_user.organization_id
        if organization_id is None:
            raise AuthorizationError("User has no organization")

        engagement = await self._engagement_repository.get_for_organization(
            request.engagement_id, organization_id=organization_id
        )
        if engagement is None:
            raise NotFoundError(f"Engagement {request.engagement_id} not found")

        # engagement.id is always populated here: it came from
        # get_for_organization(), which only ever returns persisted rows.
        # The domain type is Optional only to also cover the
        # pre-persistence state EngagementService.create() constructs.
        assert engagement.id is not None
        document_id = uuid4()
        # The object key is built from the *trusted* organization id, not
        # from the row we just read: the storage path is server-derived
        # tenant metadata and must not depend on a value that travelled
        # through the database on the way here.
        object_key = _build_object_key(organization_id, engagement.id, document_id)

        try:
            await self._storage.put(object_key, request.content, _PDF_CONTENT_TYPE)
        except StorageError as exc:
            raise PersistenceError("Unable to store the uploaded document") from exc

        now = datetime.now(timezone.utc)
        try:
            return await self._document_repository.create(
                Document(
                    id=document_id,
                    filename=sanitized_filename,
                    storage_path=object_key,
                    processing_status="PENDING",
                    engagement_id=engagement.id,
                    created_at=now,  # placeholder; the DB-generated value wins on refresh
                    updated_at=now,
                )
            )
        except (NotFoundError, PersistenceError):
            await self._compensate(object_key)
            raise

    def _validate_pdf(self, request: DocumentUploadInput) -> None:
        if not request.original_filename.lower().endswith(".pdf"):
            raise ValidationError("file must have a .pdf extension")
        if request.declared_content_type.lower() != _PDF_CONTENT_TYPE:
            raise ValidationError(f"file must be declared as {_PDF_CONTENT_TYPE}")
        if not request.content:
            raise ValidationError("file must not be empty")
        if not request.content.startswith(_PDF_MAGIC_BYTES):
            raise ValidationError("file content does not match the PDF format")
        if len(request.content) > self._max_upload_size_bytes:
            raise ValidationError(
                f"file exceeds the maximum allowed size of {self._max_upload_size_bytes} bytes"
            )

    async def _compensate(self, object_key: str) -> None:
        try:
            await self._storage.delete(object_key)
        except StorageError:
            logger.error("Failed to compensate-delete orphaned storage object: %s", object_key)
