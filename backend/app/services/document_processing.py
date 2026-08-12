"""Document processing use case: transforms an uploaded PDF into
persisted extracted text and chunks, ready for future AI processing.

Deliberately framework-independent: no FastAPI import anywhere in this
module. Depends only on repository/storage/unit-of-work interfaces.

MVP Slice 3 (Organization Data Isolation) changed how the tenant
boundary is enforced here. Previously this service loaded the Document
unscoped, loaded its Engagement unscoped, and compared
``engagement.organization_id`` to ``current_user.organization_id`` in
Python -- then performed three further writes (``begin_processing``,
``update_status``, ``complete_processing``) addressed by document id
alone. Two consequences were fixed:

* the mismatch raised ``AuthorizationError`` (403) while a nonexistent
  document raised ``NotFoundError`` (404), so an attacker holding a
  valid Document UUID could tell another organization's document apart
  from a made-up one. Both now return 404, matching the
  indistinguishable-not-found convention Sprint 3.5.1 established for
  Organization/Engagement and Sprint 3.6A adopted for embeddings;
* the tenant predicate now lives in each statement (see
  ``IDocumentRepository``), so no write can address a row outside the
  caller's organization even if reached by a future code path that
  forgets to check first.

``IEngagementRepository`` is no longer a dependency of this service: the
ownership chain it was used to walk by hand is now resolved by the
repository's own SQL join.

Pipeline: load Document tenant-scoped -> atomically claim PENDING
(``begin_processing``, its own immediately-committed transaction) ->
retrieve PDF bytes from storage -> write a secure OS temp file ->
extract text (existing, unmodified extractor) -> conservatively
normalize -> chunk (existing, unmodified chunker) -> persist
extracted_text + chunks + PROCESSED status in one transaction
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
        extracted_text_repository: IExtractedTextRepository,
        chunk_repository: IDocumentChunkRepository,
        storage: IDocumentStorage,
        unit_of_work: IProcessingUnitOfWork,
    ) -> None:
        self._document_repository = document_repository
        self._extracted_text_repository = extracted_text_repository
        self._chunk_repository = chunk_repository
        self._storage = storage
        self._unit_of_work = unit_of_work

    async def process(self, document_id: UUID, current_user: User) -> Document:
        # Fail closed: a profile with no organization has no tenant scope
        # at all, so there is no document it may process. Never a default
        # or first-organization fallback.
        organization_id = current_user.organization_id
        if organization_id is None:
            raise AuthorizationError("User has no organization")

        document = await self._document_repository.get_for_organization(
            document_id, organization_id=organization_id
        )
        if document is None:
            raise NotFoundError(f"Document {document_id} not found")

        # Atomic claim -- its own, immediately-committed transaction, and
        # itself tenant-scoped rather than trusting the read above. From
        # this point on the Document is PROCESSING and must end in either
        # PROCESSED or FAILED; it must never be left stuck in PROCESSING.
        claimed_document = await self._document_repository.begin_processing(
            document_id, organization_id=organization_id
        )

        try:
            return await self._process_claimed_document(
                claimed_document, organization_id=organization_id
            )
        except Exception as exc:
            await self._unit_of_work.rollback()
            try:
                await self._document_repository.update_status(
                    document_id, "FAILED", organization_id=organization_id
                )
            except Exception as status_exc:
                logger.error(
                    "Failed to persist FAILED status for document %s after "
                    "processing error %r: %r",
                    document_id,
                    exc,
                    status_exc,
                )
            raise _map_to_app_error(exc) from exc

    async def _process_claimed_document(
        self, document: Document, *, organization_id: UUID
    ) -> Document:
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
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    created_at=None,
                )
                for chunk in text_chunks
            ]
        )
        processed_document = await self._document_repository.complete_processing(
            document.id, organization_id=organization_id
        )
        await self._unit_of_work.commit()
        return processed_document
