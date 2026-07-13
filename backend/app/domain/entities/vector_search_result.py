"""Pure domain read-model for one tenant-scoped vector similarity match.

Deliberately not a persisted entity -- it is the composed, already-safe
result shape ``IDocumentChunkEmbeddingRepository.search()`` returns
(joined from ``document_chunk_embeddings`` and ``document_chunks``), and
the exact shape ``VectorRetrievalService`` hands back to callers. It
never carries the raw vector, ``content_hash``, provider credentials, or
any other tenant's data -- only what is safe to return over the API.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class VectorSearchResult:
    chunk_id: UUID
    document_id: UUID
    engagement_id: UUID
    chunk_index: int
    content: str
    char_start: int
    char_end: int
    similarity_score: float
