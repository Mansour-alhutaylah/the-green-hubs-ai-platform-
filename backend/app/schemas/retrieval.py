"""Pydantic request/response models for the vector retrieval endpoint.

``organization_id`` is deliberately not a field here at all -- it can
never be accepted from a client, only derived from ``current_user``
inside the router/service.
"""

from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RetrievalSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=8000)
    top_k: int = Field(ge=1, le=50)
    engagement_id: UUID | None = None
    document_id: UUID | None = None

    @field_validator("query")
    @classmethod
    def _validate_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be blank")
        return stripped


class RetrievalResultItem(BaseModel):
    chunk_id: UUID
    document_id: UUID
    engagement_id: UUID
    chunk_index: int
    content: str
    similarity_score: float
    char_start: int
    char_end: int


class RetrievalSearchResponse(BaseModel):
    items: list[RetrievalResultItem]
