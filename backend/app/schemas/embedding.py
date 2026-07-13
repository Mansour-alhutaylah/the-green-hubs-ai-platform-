"""Pydantic response model for the embedding generation endpoint.

Deliberately a summary only -- counts, never vectors, never individual
row error messages. See ``EmbeddingGenerationSummary`` (the domain
dataclass this mirrors) for what each count means.
"""

from uuid import UUID

from pydantic import BaseModel


class EmbeddingGenerationSummaryResponse(BaseModel):
    document_id: UUID
    total_chunks: int
    newly_completed: int
    already_completed: int
    failed: int
    in_progress: int
    conflicts: int
