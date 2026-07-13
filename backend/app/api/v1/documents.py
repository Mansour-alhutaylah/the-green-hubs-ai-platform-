"""Document upload and processing endpoints.

Upload converts the HTTP-specific multipart input (``UploadFile``) into
a framework-independent ``DocumentUploadInput`` before ever calling
``DocumentUploadService`` -- the service itself never imports FastAPI.

``_read_bounded`` reads the upload in fixed-size chunks, stopping the
instant the configured maximum is exceeded (never buffering more than
that plus one chunk of overshoot), and reliably closes the file in a
``finally`` block regardless of outcome.

Processing (Sprint 3.5) is a deliberately separate endpoint and a
deliberately separate service (``DocumentProcessingService``) -- upload
never triggers processing automatically, and this router never imports
anything from ``document_upload.py`` beyond what it already did.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.deps import (
    get_app_settings,
    get_current_user,
    get_document_processing_service,
    get_document_upload_service,
    get_embedding_generation_service,
)
from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.domain.entities.document import Document
from app.domain.entities.user import User
from app.schemas.document import DocumentResponse
from app.schemas.embedding import EmbeddingGenerationSummaryResponse
from app.services.document_processing import DocumentProcessingService
from app.services.document_upload import DocumentUploadInput, DocumentUploadService
from app.services.embedding_generation import EmbeddingGenerationService

router = APIRouter(prefix="/documents", tags=["documents"])

_CHUNK_SIZE_BYTES = 64 * 1024


async def _read_bounded(file: UploadFile, max_size_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            chunk = await file.read(_CHUNK_SIZE_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > max_size_bytes:
                raise ValidationError(
                    f"File exceeds the maximum allowed size of {max_size_bytes} bytes"
                )
            chunks.append(chunk)
    finally:
        await file.close()
    return b"".join(chunks)


def _to_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        engagement_id=document.engagement_id,
        filename=document.filename,
        processing_status=document.processing_status,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Engagement not found"},
        403: {"description": "Not authorized for this engagement"},
    },
    summary="Upload a PDF document to an engagement",
)
async def upload_document(
    engagement_id: UUID = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    service: DocumentUploadService = Depends(get_document_upload_service),
    settings: Settings = Depends(get_app_settings),
) -> DocumentResponse:
    content = await _read_bounded(file, settings.max_upload_size_bytes)
    upload_input = DocumentUploadInput(
        engagement_id=engagement_id,
        original_filename=file.filename or "",
        declared_content_type=file.content_type or "",
        content=content,
    )
    document = await service.upload(upload_input, current_user=current_user)
    return _to_response(document)


@router.post(
    "/{document_id}/process",
    response_model=DocumentResponse,
    responses={
        404: {"description": "Document or Engagement not found"},
        403: {"description": "Not authorized for this engagement"},
        409: {"description": "Document is not in a state that can begin processing"},
    },
    summary="Process an uploaded PDF document into extracted text and chunks",
)
async def process_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    service: DocumentProcessingService = Depends(get_document_processing_service),
) -> DocumentResponse:
    document = await service.process(document_id, current_user)
    return _to_response(document)


@router.post(
    "/{document_id}/embeddings",
    response_model=EmbeddingGenerationSummaryResponse,
    responses={
        404: {"description": "Document not found"},
        403: {"description": "Not authorized for this document"},
        409: {"description": "Document has not been processed yet"},
    },
    summary="Idempotently generate embeddings for a processed document's chunks",
)
async def generate_document_embeddings(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    service: EmbeddingGenerationService = Depends(get_embedding_generation_service),
) -> EmbeddingGenerationSummaryResponse:
    summary = await service.generate_for_document(document_id, current_user)
    return EmbeddingGenerationSummaryResponse(
        document_id=summary.document_id,
        total_chunks=summary.total_chunks,
        newly_completed=summary.newly_completed,
        already_completed=summary.already_completed,
        failed=summary.failed,
        in_progress=summary.in_progress,
        conflicts=summary.conflicts,
    )
