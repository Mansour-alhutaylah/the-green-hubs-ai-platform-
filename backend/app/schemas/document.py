"""Pydantic response models for the Document upload, list, and detail
endpoints.

``storage_path`` is deliberately omitted from every response here: it is
an internal storage detail with no client-facing use this sprint. A
future, deliberately designed download endpoint (e.g. returning a
signed URL) is the right place for retrieval -- not exposing the raw
object key now.

``DocumentProcessingStatus`` (Sprint 3, Document Read API Foundation)
exists purely to give the ``processing_status`` list-filter query
parameter 422 validation -- ``documents.processing_status`` itself is a
plain, un-enumerated ``str`` column (see ``Document``'s domain entity
docstring), so this is not a duplicate of any database or domain enum,
just the same conventional values every write path already produces
(``SQLAlchemyDocumentRepository._STATE_TRANSITION_MESSAGES``).

``DocumentReadResponse`` is used both as a ``DocumentListResponse`` item
and as the ``GET /api/v1/documents/{document_id}`` response body: the
sprint's required field set is identical for both, so one schema
serves both, rather than two structurally-identical models.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: UUID
    engagement_id: UUID
    filename: str
    processing_status: str
    created_at: datetime
    updated_at: datetime


class DocumentProcessingStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class EmbeddingSummaryResponse(BaseModel):
    total_chunks: int
    processing: int
    completed: int
    failed: int
    is_complete: bool


class AnalysisSummaryResponse(BaseModel):
    id: UUID
    status: str
    analysis_type: str
    created_at: datetime | None
    completed_at: datetime | None
    overall_confidence: float | None


class DocumentReadResponse(BaseModel):
    id: UUID
    engagement_id: UUID
    filename: str
    processing_status: str
    created_at: datetime
    updated_at: datetime
    has_extracted_text: bool
    chunk_count: int
    embedding_summary: EmbeddingSummaryResponse
    latest_analysis_summary: AnalysisSummaryResponse | None


class DocumentListResponse(BaseModel):
    items: list[DocumentReadResponse]
    total: int
    limit: int
    offset: int
