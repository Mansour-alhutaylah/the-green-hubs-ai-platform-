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

``list_documents``/``get_document`` (Sprint 3, Document Read API
Foundation) never accept ``organization_id`` from the client in any
form (query, header, body) -- tenant scope always comes from
``current_user`` inside ``DocumentReadService``, matching every other
tenant-scoped router in this codebase.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.api.deps import (
    get_app_settings,
    get_current_user,
    get_document_processing_service,
    get_document_read_service,
    get_document_upload_service,
    get_embedding_generation_service,
    require_permission,
)
from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.domain.entities.document import Document
from app.domain.entities.document_read_model import DocumentReadModel
from app.domain.entities.user import User
from app.domain.security import Permission
from app.schemas.document import (
    AnalysisSummaryResponse,
    DocumentListResponse,
    DocumentProcessingStatus,
    DocumentReadResponse,
    DocumentResponse,
    EmbeddingSummaryResponse,
)
from app.schemas.embedding import EmbeddingGenerationSummaryResponse
from app.services.document_processing import DocumentProcessingService
from app.services.document_read import DocumentReadService
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


def _to_read_response(document: DocumentReadModel) -> DocumentReadResponse:
    latest_analysis_summary = document.latest_analysis_summary
    return DocumentReadResponse(
        id=document.id,
        engagement_id=document.engagement_id,
        filename=document.filename,
        processing_status=document.processing_status,
        created_at=document.created_at,
        updated_at=document.updated_at,
        has_extracted_text=document.has_extracted_text,
        chunk_count=document.chunk_count,
        embedding_summary=EmbeddingSummaryResponse(
            total_chunks=document.embedding_summary.total_chunks,
            processing=document.embedding_summary.processing,
            completed=document.embedding_summary.completed,
            failed=document.embedding_summary.failed,
            is_complete=document.embedding_summary.is_complete,
        ),
        latest_analysis_summary=(
            AnalysisSummaryResponse(
                id=latest_analysis_summary.id,
                status=latest_analysis_summary.status,
                analysis_type=latest_analysis_summary.analysis_type,
                created_at=latest_analysis_summary.created_at,
                completed_at=latest_analysis_summary.completed_at,
                overall_confidence=latest_analysis_summary.overall_confidence,
            )
            if latest_analysis_summary is not None
            else None
        ),
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
    current_user: User = Depends(require_permission(Permission.DOCUMENT_UPLOAD)),
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
    current_user: User = Depends(require_permission(Permission.DOCUMENT_PROCESS)),
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
    current_user: User = Depends(require_permission(Permission.DOCUMENT_PROCESS)),
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


@router.get(
    "",
    response_model=DocumentListResponse,
    responses={403: {"description": "User has no organization"}, 404: {"description": "Engagement not found"}},
    summary="List Documents belonging to the caller's own organization",
)
async def list_documents(
    engagement_id: UUID | None = Query(None),
    processing_status: DocumentProcessingStatus | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    service: DocumentReadService = Depends(get_document_read_service),
) -> DocumentListResponse:
    items, total = await service.list(
        current_user,
        engagement_id=engagement_id,
        processing_status=processing_status.value if processing_status is not None else None,
        limit=limit,
        offset=offset,
    )
    return DocumentListResponse(
        items=[_to_read_response(item) for item in items], total=total, limit=limit, offset=offset
    )


@router.get(
    "/{document_id}",
    response_model=DocumentReadResponse,
    responses={403: {"description": "User has no organization"}, 404: {"description": "Document not found"}},
    summary="Retrieve a Document belonging to the caller's own organization",
)
async def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    service: DocumentReadService = Depends(get_document_read_service),
) -> DocumentReadResponse:
    document = await service.get(document_id, current_user)
    return _to_read_response(document)
