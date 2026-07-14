"""Unit tests for tenant-safe request-hash computation
(Mandatory Correction 1)."""

import uuid
from decimal import Decimal

from app.services.analysis.request_hash import compute_request_hash, normalize_query_text

DIGEST_HEX_LENGTH = 64


def _base_kwargs(**overrides: object) -> dict:
    kwargs: dict = dict(
        organization_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        engagement_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        document_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        analysis_type="sustainability_summary",
        query_text="scope 1 emissions",
        provider="openai",
        model="gpt-4o-mini",
        prompt_template_version="v1",
        output_schema_version="v1",
        temperature=Decimal("0.10"),
        retrieval_top_k=10,
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_model_version="",
        minimum_relevance_score=Decimal("0.500"),
    )
    kwargs.update(overrides)
    return kwargs


def test_normalize_query_text_strips_and_collapses_whitespace() -> None:
    assert normalize_query_text("  scope   1\n\temissions  ") == "scope 1 emissions"


def test_hash_is_a_64_character_hex_digest() -> None:
    digest = compute_request_hash(**_base_kwargs())
    assert len(digest) == DIGEST_HEX_LENGTH
    assert all(c in "0123456789abcdef" for c in digest)


def test_identical_inputs_produce_identical_hash() -> None:
    a = compute_request_hash(**_base_kwargs())
    b = compute_request_hash(**_base_kwargs())
    assert a == b


def test_differently_whitespaced_but_equivalent_query_text_hashes_identically() -> None:
    a = compute_request_hash(**_base_kwargs(query_text="scope 1 emissions"))
    b = compute_request_hash(**_base_kwargs(query_text="  scope   1 emissions "))
    assert a == b


def test_different_organization_id_changes_hash() -> None:
    a = compute_request_hash(**_base_kwargs())
    b = compute_request_hash(**_base_kwargs(organization_id=uuid.uuid4()))
    assert a != b


def test_different_document_id_changes_hash() -> None:
    a = compute_request_hash(**_base_kwargs())
    b = compute_request_hash(**_base_kwargs(document_id=uuid.uuid4()))
    assert a != b


def test_none_document_id_differs_from_any_document_id() -> None:
    a = compute_request_hash(**_base_kwargs(document_id=None))
    b = compute_request_hash(**_base_kwargs())
    assert a != b


def test_different_query_text_changes_hash() -> None:
    a = compute_request_hash(**_base_kwargs(query_text="scope 1 emissions"))
    b = compute_request_hash(**_base_kwargs(query_text="scope 2 emissions"))
    assert a != b


def test_different_analysis_type_changes_hash() -> None:
    a = compute_request_hash(**_base_kwargs(analysis_type="sustainability_summary"))
    b = compute_request_hash(**_base_kwargs(analysis_type="other_type"))
    assert a != b


def test_different_provider_changes_hash() -> None:
    a = compute_request_hash(**_base_kwargs())
    b = compute_request_hash(**_base_kwargs(provider="anthropic"))
    assert a != b


def test_different_model_changes_hash() -> None:
    a = compute_request_hash(**_base_kwargs())
    b = compute_request_hash(**_base_kwargs(model="gpt-4o"))
    assert a != b


def test_different_prompt_template_version_changes_hash() -> None:
    a = compute_request_hash(**_base_kwargs())
    b = compute_request_hash(**_base_kwargs(prompt_template_version="v2"))
    assert a != b


def test_different_output_schema_version_changes_hash() -> None:
    a = compute_request_hash(**_base_kwargs())
    b = compute_request_hash(**_base_kwargs(output_schema_version="v2"))
    assert a != b


def test_different_temperature_changes_hash() -> None:
    a = compute_request_hash(**_base_kwargs())
    b = compute_request_hash(**_base_kwargs(temperature=Decimal("0.20")))
    assert a != b


def test_different_retrieval_top_k_changes_hash() -> None:
    a = compute_request_hash(**_base_kwargs())
    b = compute_request_hash(**_base_kwargs(retrieval_top_k=20))
    assert a != b


def test_different_embedding_provider_changes_hash() -> None:
    a = compute_request_hash(**_base_kwargs())
    b = compute_request_hash(**_base_kwargs(embedding_provider="cohere"))
    assert a != b


def test_different_embedding_model_changes_hash() -> None:
    a = compute_request_hash(**_base_kwargs())
    b = compute_request_hash(**_base_kwargs(embedding_model="text-embedding-3-large"))
    assert a != b


def test_different_embedding_model_version_changes_hash() -> None:
    a = compute_request_hash(**_base_kwargs())
    b = compute_request_hash(**_base_kwargs(embedding_model_version="v2"))
    assert a != b


def test_different_minimum_relevance_score_changes_hash() -> None:
    a = compute_request_hash(**_base_kwargs())
    b = compute_request_hash(**_base_kwargs(minimum_relevance_score=Decimal("0.700")))
    assert a != b


def test_adjacent_field_concatenation_is_not_ambiguous() -> None:
    """Guards the delimiter choice: without a delimiter, an engagement_id
    of "ab" plus a document_id of "c" would collide with an engagement_id
    of "a" plus a document_id of "bc". UUIDs can't literally do this, but
    this test proves the general adjacent-field boundary is preserved
    for the free-text fields that could."""
    a = compute_request_hash(**_base_kwargs(analysis_type="ab", query_text="c"))
    b = compute_request_hash(**_base_kwargs(analysis_type="a", query_text="bc"))
    assert a != b
