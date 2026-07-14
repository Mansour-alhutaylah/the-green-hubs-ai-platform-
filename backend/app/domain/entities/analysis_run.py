"""Pure domain entity for a single RAG analysis request/result.

Framework-independent. ``id``/``processing_started_at``/``created_at``/
``updated_at`` are server-generated -- ``None`` only pre-persistence,
mirroring ``DocumentChunkEmbedding``'s own convention.

``request_hash`` is computed application-side (see
``app.services.analysis.request_hash``) over every behavior-changing
input, including ``organization_id`` itself -- the tenant-safe
idempotency mechanism mandated for this sprint. ``organization_id`` and
``request_hash`` together are the natural key
(``uq_analysis_runs_organization_request_hash``, migration
``da0298a9c722``): identical requests within one organization collide
and reuse the same run; identical requests across organizations never
collide.

``structured_output`` is ``None`` unless ``status == 'COMPLETED'`` --
see ``analysis_runs``' combined status/column CHECK constraint for the
database-level version of this invariant.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass
class AnalysisRun:
    id: UUID | None
    organization_id: UUID
    engagement_id: UUID
    document_id: UUID | None
    requested_by_user_id: UUID
    analysis_type: str
    query_text: str | None
    provider: str
    model: str
    prompt_template_version: str
    output_schema_version: str
    temperature: Decimal
    retrieval_top_k: int
    embedding_provider: str
    embedding_model: str
    embedding_model_version: str
    minimum_relevance_score: Decimal
    request_hash: str
    status: str
    structured_output: dict | None
    error_message: str | None
    insufficient_evidence_reason: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    estimated_cost: Decimal | None
    processing_started_at: datetime | None
    attempt_count: int
    created_at: datetime | None
    updated_at: datetime | None
    completed_at: datetime | None
