"""Pydantic request/response models for the RAG analysis endpoints.

``organization_id`` is deliberately not a field anywhere here, request
or response -- it can never be accepted from a client (always derived
from ``current_user`` inside ``RagAnalysisService``), and is omitted
from responses too since it adds nothing the caller doesn't already
know about their own session.

Every ``source_keys``-bearing item in the LLM's structured output has
already been rewritten to ``citation_ids`` (real, persisted
``analysis_source_references`` UUIDs) by ``RagAnalysisService`` before
it ever reaches this layer -- see ``_remap_source_keys_to_citation_ids``.
No temporary ``SOURCE_n`` key, raw vector, or provider response body is
ever exposed here.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AnalyzeRequest(BaseModel):
    analysis_type: str = Field(min_length=1, max_length=100)
    query_text: str = Field(min_length=1, max_length=2000)

    @field_validator("query_text")
    @classmethod
    def _validate_query_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query_text must not be blank")
        return stripped


class MetricValueOut(BaseModel):
    name: str
    status: str
    value: str | None = None
    unit: str | None = None
    period: str | None = None
    citation_ids: list[UUID] = Field(default_factory=list)


class FindingOut(BaseModel):
    statement: str
    citation_ids: list[UUID] = Field(default_factory=list)


class RecommendationOut(BaseModel):
    statement: str
    citation_ids: list[UUID] = Field(default_factory=list)


class StructuredAnalysisOut(BaseModel):
    analysis_type: str
    evidence_status: str
    insufficient_evidence_reason: str | None = None
    executive_summary: str
    reporting_period: str | None = None
    detected_topics: list[str] = Field(default_factory=list)
    reported_metrics: list[MetricValueOut] = Field(default_factory=list)
    key_findings: list[FindingOut] = Field(default_factory=list)
    recommendations: list[RecommendationOut] = Field(default_factory=list)
    overall_confidence: float


class CitationOut(BaseModel):
    id: UUID
    document_id: UUID
    chunk_index: int
    char_start: int
    char_end: int
    quoted_snippet: str
    citation_order: int
    relevance_score: float


class AnalysisRunResponse(BaseModel):
    analysis_run_id: UUID
    engagement_id: UUID
    document_id: UUID | None
    status: str
    analysis_type: str
    structured_output: StructuredAnalysisOut | None
    insufficient_evidence_reason: str | None
    error_message: str | None
    citations: list[CitationOut]
    created_at: datetime | None
    updated_at: datetime | None
    completed_at: datetime | None
