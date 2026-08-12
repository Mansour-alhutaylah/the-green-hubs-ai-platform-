"""Pure domain entities for tenant-safe Document read projections.

Sprint 3 (Document Read API Foundation). Distinct from ``Document``
(``document.py``) rather than an extension of it: these entities carry
derived, computed-at-query-time data (chunk counts, embedding lifecycle
aggregates, the latest analysis run) that is never persisted on the
``documents`` row itself, so folding it into the write-path ``Document``
entity would blur "what is stored" with "what is computed for display".

``EmbeddingSummary.total_chunks`` counts ``document_chunk_embeddings``
rows for the document (i.e. embedding attempts), not ``document_chunks``
rows -- that distinct, real count is ``DocumentReadModel.chunk_count``.
Exposing both, undisguised, lets a caller compare them to notice a
partially-attempted embedding pass without this layer fabricating a
"partially_completed" status that has no backing column anywhere.

``AnalysisSummary.overall_confidence`` is ``None`` unless the run's
``structured_output`` actually contains it (only possible when
``status == "COMPLETED"``, per ``analysis_runs``' own status/column CHECK
constraint) -- never guessed or defaulted.

MVP Slice 4 (Evidence Review Lifecycle) adds the five evidence fields.
Unlike everything else here they are *stored* columns rather than
derived aggregates, and they duplicate what ``DocumentEvidence``
carries -- deliberately, because a documents list has to be able to show
"which of these are approved evidence, and who approved them" without
issuing one extra query per row. ``DocumentEvidence`` remains the write
path's return type; this is the read projection's copy of the same
current-state facts, produced by the same single query as the rest of
the row.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.evidence.lifecycle import EvidenceStatus


@dataclass(frozen=True)
class EmbeddingSummary:
    total_chunks: int
    processing: int
    completed: int
    failed: int
    is_complete: bool


@dataclass(frozen=True)
class AnalysisSummary:
    id: UUID
    status: str
    analysis_type: str
    created_at: datetime | None
    completed_at: datetime | None
    overall_confidence: float | None


@dataclass(frozen=True)
class DocumentReadModel:
    id: UUID
    engagement_id: UUID
    filename: str
    processing_status: str
    created_at: datetime
    updated_at: datetime
    has_extracted_text: bool
    chunk_count: int
    embedding_summary: EmbeddingSummary
    latest_analysis_summary: AnalysisSummary | None
    evidence_status: EvidenceStatus
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_reason: str | None
    superseded_by_document_id: UUID | None
