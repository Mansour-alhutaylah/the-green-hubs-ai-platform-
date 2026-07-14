"""Unit tests for ``StructuredAnalysisResult`` validation."""

import pytest
from pydantic import ValidationError

from app.services.analysis.structured_output import StructuredAnalysisResult

_VALID = {
    "analysis_type": "sustainability_summary",
    "evidence_status": "sufficient",
    "insufficient_evidence_reason": None,
    "executive_summary": "The company reports on Scope 1 emissions.",
    "reporting_period": "FY2025",
    "detected_topics": ["emissions"],
    "reported_metrics": [
        {
            "name": "Scope 1 emissions",
            "status": "stated",
            "value": "1000",
            "unit": "tCO2e",
            "period": "FY2025",
            "source_keys": ["SOURCE_1"],
        }
    ],
    "key_findings": [{"statement": "Emissions decreased.", "source_keys": ["SOURCE_1"]}],
    "recommendations": [{"statement": "Continue current trend.", "source_keys": ["SOURCE_1"]}],
    "overall_confidence": 0.8,
}


def test_valid_payload_parses() -> None:
    result = StructuredAnalysisResult.model_validate(_VALID)
    assert result.evidence_status == "sufficient"
    assert result.all_source_keys() == {"SOURCE_1"}


def test_all_source_keys_deduplicates_across_items() -> None:
    payload = dict(_VALID)
    payload["key_findings"] = [
        {"statement": "A", "source_keys": ["SOURCE_1", "SOURCE_2"]},
        {"statement": "B", "source_keys": ["SOURCE_1"]},
    ]
    result = StructuredAnalysisResult.model_validate(payload)
    assert result.all_source_keys() == {"SOURCE_1", "SOURCE_2"}


def test_malformed_source_key_format_rejected() -> None:
    payload = dict(_VALID)
    payload["key_findings"] = [{"statement": "A", "source_keys": ["not-a-source-key"]}]
    with pytest.raises(ValidationError):
        StructuredAnalysisResult.model_validate(payload)


def test_insufficient_evidence_status_requires_reason() -> None:
    payload = dict(_VALID)
    payload["evidence_status"] = "insufficient"
    payload["insufficient_evidence_reason"] = None
    with pytest.raises(ValidationError):
        StructuredAnalysisResult.model_validate(payload)


def test_insufficient_evidence_status_with_reason_is_valid() -> None:
    payload = dict(_VALID)
    payload["evidence_status"] = "insufficient"
    payload["insufficient_evidence_reason"] = "No relevant disclosures found."
    result = StructuredAnalysisResult.model_validate(payload)
    assert result.evidence_status == "insufficient"


def test_confidence_out_of_range_rejected() -> None:
    payload = dict(_VALID)
    payload["overall_confidence"] = 1.5
    with pytest.raises(ValidationError):
        StructuredAnalysisResult.model_validate(payload)


def test_invalid_metric_status_rejected() -> None:
    payload = dict(_VALID)
    payload["reported_metrics"] = [
        {"name": "X", "status": "definitely_true", "source_keys": []}
    ]
    with pytest.raises(ValidationError):
        StructuredAnalysisResult.model_validate(payload)


def test_missing_executive_summary_rejected() -> None:
    payload = dict(_VALID)
    payload["executive_summary"] = ""
    with pytest.raises(ValidationError):
        StructuredAnalysisResult.model_validate(payload)


def test_empty_source_keys_are_allowed_when_no_evidence_cited() -> None:
    payload = dict(_VALID)
    payload["key_findings"] = [{"statement": "General observation.", "source_keys": []}]
    result = StructuredAnalysisResult.model_validate(payload)
    assert result.all_source_keys() == {"SOURCE_1"}  # still from reported_metrics/recommendations
