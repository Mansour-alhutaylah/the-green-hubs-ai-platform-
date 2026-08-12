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

MVP Slice 4 (Evidence Review Lifecycle) adds the evidence request/
response models. Three things about them are deliberate:

* there is **no** ``evidence_status`` field on any *request* model here.
  The lifecycle is driven by four named commands, each its own route;
  a client cannot name a target state, so it cannot ask for a
  transition the state machine does not offer;
* there is likewise no ``reviewed_by`` and no ``reviewed_at`` on any
  request model. Both are derived server-side (authenticated profile,
  database clock), and the absence of the fields is what makes
  supplying them impossible rather than merely ignored;
* ``reason`` is validated here *and* re-validated in
  ``EvidenceReviewService``. This layer exists to return a clean 422
  early; the service's copy is the authoritative one, because it is the
  check a caller that never builds a Pydantic model still passes.
  ``MAX_REVIEW_REASON_CHARS`` is imported from the lifecycle module so
  the two bounds cannot drift apart.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.domain.evidence.lifecycle import MAX_REVIEW_REASON_CHARS, EvidenceStatus


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
    evidence_status: EvidenceStatus
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_reason: str | None
    superseded_by_document_id: UUID | None


class DocumentListResponse(BaseModel):
    items: list[DocumentReadResponse]
    total: int
    limit: int
    offset: int


def _require_non_blank_reason(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("reason must not be blank")
    return stripped


class EvidenceVerifyRequest(BaseModel):
    """Body for ``verify``. Wholly optional -- the route accepts none.

    ``reason`` is a note, not a justification: an approval's meaning is
    the approval. A blank or whitespace-only note is normalized away by
    the service rather than rejected, since nothing depends on it."""

    reason: str | None = Field(default=None, max_length=MAX_REVIEW_REASON_CHARS)


class EvidenceReasonRequest(BaseModel):
    """Body for ``reject`` and ``restrict``. The reason is mandatory.

    ``min_length=1`` rejects ``""`` and the validator rejects
    whitespace-only input, so neither form of "no reason" can reach the
    stored decision. An omitted or explicitly null ``reason`` fails the
    plain ``str`` type check with 422 -- the same distinction
    ``EngagementUpdateRequest`` relies on."""

    reason: str = Field(min_length=1, max_length=MAX_REVIEW_REASON_CHARS)

    @field_validator("reason")
    @classmethod
    def _validate_reason(cls, value: str) -> str:
        return _require_non_blank_reason(value)


class EvidenceSupersedeRequest(EvidenceReasonRequest):
    """Body for ``supersede``: the same mandatory reason, plus an
    optional successor.

    ``superseded_by_document_id`` is optional because a reviewer may
    mark a document obsolete with no replacement to point at. When
    supplied it must be a document in the caller's own organization and
    not this document itself -- both enforced server-side, the second
    within the transition's own SQL predicate."""

    superseded_by_document_id: UUID | None = None


class DocumentEvidenceResponse(BaseModel):
    """The document's current evidence decision after the command.

    Returned by all four review routes, including the idempotent-repeat
    case -- where it carries the *original* reviewer and timestamp, not
    the retrying caller's."""

    id: UUID
    engagement_id: UUID
    evidence_status: EvidenceStatus
    # `str | None` mirrors DocumentEvidence, whose type deliberately
    # admits a missing processing state so the approval precondition
    # fails closed rather than looking impossible.
    processing_status: str | None
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_reason: str | None
    superseded_by_document_id: UUID | None
    updated_at: datetime
