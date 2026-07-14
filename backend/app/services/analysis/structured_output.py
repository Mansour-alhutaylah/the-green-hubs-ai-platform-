"""Pydantic validation models for the LLM's structured sustainability
analysis output (``output_schema_version`` "v1").

Deliberately not a domain entity: domain entities in this codebase are
plain dataclasses, but this model's whole purpose is validating
untrusted, semi-structured JSON from an external provider -- the same
"validate at the boundary" role Pydantic already plays for API request
bodies, just applied to a different untrusted boundary (the LLM
response instead of the HTTP request).

Field-level validation only checks *shape* (each ``source_keys`` entry
looks like ``SOURCE_<n>``). Whether a given key was actually part of the
assembled context is a service-level concern (``RagAnalysisService``),
since only the caller holds the per-request ``source_map`` -- exactly
the same shape/membership split ``LLMGateway``'s schema-agnostic
``validator`` callback was designed around.

``analysis_type`` here is intentionally left as a free string per
CLAUDE.md's str-first-then-Enum convention: only one analysis type
(``sustainability_summary``) is implemented this sprint (see
``RagAnalysisService``'s allow-list), so an Enum would be premature.
"""

import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

_SOURCE_KEY_PATTERN = re.compile(r"^SOURCE_\d+$")


def _validate_source_key_format(value: list[str]) -> list[str]:
    for key in value:
        if not _SOURCE_KEY_PATTERN.match(key):
            raise ValueError(f"invalid source key format: {key!r}")
    return value


class _SourceKeyedItem(BaseModel):
    source_keys: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_source_keys(self) -> "_SourceKeyedItem":
        _validate_source_key_format(self.source_keys)
        return self


class MetricValue(_SourceKeyedItem):
    name: str = Field(min_length=1)
    status: Literal["stated", "not_stated", "uncertain"]
    value: str | None = None
    unit: str | None = None
    period: str | None = None


class Finding(_SourceKeyedItem):
    statement: str = Field(min_length=1)


class Recommendation(_SourceKeyedItem):
    statement: str = Field(min_length=1)


class StructuredAnalysisResult(BaseModel):
    analysis_type: str = Field(min_length=1)
    evidence_status: Literal["sufficient", "insufficient"]
    insufficient_evidence_reason: str | None = None
    executive_summary: str = Field(min_length=1)
    reporting_period: str | None = None
    detected_topics: list[str] = Field(default_factory=list)
    reported_metrics: list[MetricValue] = Field(default_factory=list)
    key_findings: list[Finding] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_insufficient_evidence_reason(self) -> "StructuredAnalysisResult":
        if self.evidence_status == "insufficient" and not (
            self.insufficient_evidence_reason or ""
        ).strip():
            raise ValueError(
                "insufficient_evidence_reason is required when evidence_status is 'insufficient'"
            )
        return self

    def all_source_keys(self) -> set[str]:
        keys: set[str] = set()
        for item in (*self.reported_metrics, *self.key_findings, *self.recommendations):
            keys.update(item.source_keys)
        return keys
