"""Document upload endpoint.

Converts the HTTP-specific multipart input (``UploadFile``) into a
framework-independent ``DocumentUploadInput`` before ever calling
``DocumentUploadService`` -- the service itself never imports FastAPI.

``_read_bounded`` reads the upload in fixed-size chunks, stopping the
instant the configured maximum is exceeded (never buffering more than
that plus one chunk of overshoot), and reliably closes the file in a
``finally`` block regardless of outcome.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.deps import get_app_settings, get_current_user, get_document_upload_service
from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.domain.entities.document import Document
from app.domain.entities.user import User
from app.schemas.document import DocumentResponse
from app.services.document_upload import DocumentUploadInput, DocumentUploadService

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
