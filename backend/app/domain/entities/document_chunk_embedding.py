"""Pure domain entity for a single chunk's embedding attempt/result.

Framework-independent. ``id``/``processing_started_at``/``created_at``/
``updated_at`` are server-generated -- ``None`` only pre-persistence
(this entity is normally only ever constructed from a persisted row, but
the ``Optional`` typing stays honest about that boundary, mirroring
``Document``'s sibling entities).

``embedding`` is ``None`` unless ``status == "COMPLETED"`` -- see
``document_chunk_embeddings``' combined status/column CHECK constraint
(migration ``3f3acc7fc556``) for the database-level version of this same
invariant. ``document_id``/``engagement_id``/``organization_id`` are
never independently constructed by application code from untrusted
input; they only ever arrive already-populated from the repository,
which itself derives them from ``chunk_id``'s real lineage at insert
time (see ``IDocumentChunkEmbeddingRepository``).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence
from uuid import UUID


@dataclass
class DocumentChunkEmbedding:
    id: UUID | None
    chunk_id: UUID
    document_id: UUID
    engagement_id: UUID
    organization_id: UUID
    provider: str
    model: str
    model_version: str
    embedding_dimension: int
    embedding: Sequence[float] | None
    content_hash: str
    status: str
    error_message: str | None
    processing_started_at: datetime | None
    attempt_count: int
    created_at: datetime | None
    updated_at: datetime | None
