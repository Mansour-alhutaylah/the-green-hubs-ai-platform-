"""Document processing use case: transforms an uploaded PDF into
persisted extracted text and chunks, ready for future AI processing.

Deliberately framework-independent: no FastAPI import anywhere in this
module. Depends only on repository/storage/unit-of-work interfaces,
mirroring ``DocumentUploadService``'s exact shape -- Engagement
existence and organization-match authorization is checked here via
``IEngagementRepository`` directly (never ``EngagementService``), so
neither it nor ``OrganizationService`` needs any redesign.

Pipeline: load Document -> load Engagement -> authorize -> atomically
claim PENDING (``begin_processing``, its own immediately-committed
transaction) -> retrieve PDF bytes from storage -> write a secure OS
temp file -> extract text (existing, unmodified extractor) ->
conservatively normalize -> chunk (existing, unmodified chunker) ->
persist extracted_text + chunks + PROCESSED status in one transaction
(``IProcessingUnitOfWork``) -> return the persisted Document.

On any failure after the claim: the processing transaction is rolled
back (so no partial extracted_text/chunk rows are ever committed), then
the Document is marked FAILED in its own separate, reliable transaction
(the pre-existing, unmodified ``update_status()``) -- this always runs,
because the Document is already PROCESSING at this point and must never
be left stuck there. There is no cross-system transaction spanning
Postgres and Supabase Storage: storage retrieval failures need no
compensation (nothing was written yet), and the three DB writes use a
real database transaction (rollback, not manual row deletion).
"""

import logging
import os
import tempfile
from pathlib import Path
from uuid import UUID

from app.core.exceptions import (
    AppError,
    AuthorizationError,
    NotFoundError,
    PersistenceError,
    ValidationError,
)
from app.domain.entities.document import Document
from app.domain.entities.document_chunk import DocumentChunk
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
    StorageError,
    StorageObjectNotFoundError,
    StorageUnavailableError,
)
from app.infrastructure.documents.chunker import chunk_text
from app.infrastructure.documents.normalizer import normalize_text
from app.infrastructure.documents.text_extractor import (
    TextExtractionError,
    UnsupportedFileTypeError,
    extract_text,
)

logger = logging.getLogger(__name__)


async def _extract_text_from_bytes(pdf_bytes: bytes) -> str:
    """Writes ``pdf_bytes`` to a secure, OS-managed temp file (never the
    original filename) and calls the existing, unmodified extractor
    against it. The file is closed before extraction begins and removal is
    attempted in ``finally``, on both success and every failure path.

    Removal is best-effort: a parsing library that fails to open a
    malformed PDF can leave its own internal file handle open slightly
    longer than the Python-level call that raised, which on Windows makes
    ``unlink`` fail with ``PermissionError`` even though the underlying
    temp file is genuinely orphaned, not in normal use. Swallowing (and
    logging) that specific failure here matters: without it, the cleanup
    step itself would raise and replace -- not just accompany -- the real
    extraction error, so callers would see an unrelated OS error instead
    of the actual failure reason.
    """
    fd, temp_path_str = tempfile.mkstemp(suffix=".pdf")
    temp_path = Path(temp_path_str)
    try:
        with os.fdopen(fd, "wb") as temp_file:
            temp_file.write(pdf_bytes)
        return await extract_text(temp_path)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove temporary file %s", temp_path)


def _map_to_app_error(exc: Exception) -> AppError:
    if isinstance(exc, AppError):
        return exc
    if isinstance(exc, StorageObjectNotFoundError):
        return NotFoundError("Stored document object not found")
    if isinstance(exc, (StorageUnavailableError, StorageConfigurationError, StorageError)):
        return PersistenceError("Unable to retrieve the stored document")
    if isinstance(exc, (UnsupportedFileTypeError, TextExtractionError)):
        return ValidationError("Unable to extract text from the stored document")
    return PersistenceError("Unable to process the document")


class DocumentProcessingService:
    def __init__(
        self,
        document_repository: IDocumentRepository,
        engagement_repository: IEngagementRepository,
        extracted_text_repository: IExtractedTextRepository,
        chunk_repository: IDocumentChunkRepository,
        storage: IDocumentStorage,
        unit_of_work: IProcessingUnitOfWork,
    ) -> None:
        self._document_repository = document_repository
        self._engagement_repository = engagement_repository
        self._extracted_text_repository = extracted_text_repository
        self._chunk_repository = chunk_repository
        self._storage = storage
        self._unit_of_work = unit_of_work

    async def process(self, document_id: UUID, current_user: User) -> Document:
        document = await self._document_repository.get(document_id)
        if document is None:
            raise NotFoundError(f"Document {document_id} not found")

        engagement = await self._engagement_repository.get(document.engagement_id)
        if engagement is None:
            raise NotFoundError(f"Engagement {document.engagement_id} not found")

        if current_user.organization_id is None:
            raise AuthorizationError("User has no organization")
        if engagement.organization_id is None:
            raise AuthorizationError("Engagement has no organization")
        if current_user.organization_id != engagement.organization_id:
            raise AuthorizationError("User is not authorized for this engagement")

        # Atomic claim -- its own, immediately-committed transaction. From
        # this point on the Document is PROCESSING and must end in either
        # PROCESSED or FAILED; it must never be left stuck in PROCESSING.
        claimed_document = await self._document_repository.begin_processing(document_id)

        try:
            return await self._process_claimed_document(claimed_document)
        except Exception as exc:
            await self._unit_of_work.rollback()
            try:
                await self._document_repository.update_status(document_id, "FAILED")
            except Exception as status_exc:
                logger.error(
                    "Failed to persist FAILED status for document %s after "
                    "processing error %r: %r",
                    document_id,
                    exc,
                    status_exc,
                )
            raise _map_to_app_error(exc) from exc

    async def _process_claimed_document(self, document: Document) -> Document:
        pdf_bytes = await self._storage.get(document.storage_path)
        extracted = await _extract_text_from_bytes(pdf_bytes)
        normalized = normalize_text(extracted)

        if not normalized.strip():
            raise ValidationError("Extracted text is empty")

        text_chunks = chunk_text(normalized)
        if not text_chunks:
            raise ValidationError("No chunks were generated from the extracted text")

        await self._extracted_text_repository.create(
            ExtractedText(
                id=None,
                document_id=document.id,
                extracted_content=normalized,
                created_at=None,
            )
        )
        await self._chunk_repository.create_many(
            [
                DocumentChunk(
                    id=None,
                    document_id=document.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.text,
                    created_at=None,
                )
                for chunk in text_chunks
            ]
        )
        processed_document = await self._document_repository.complete_processing(document.id)
        await self._unit_of_work.commit()
        return processed_document
