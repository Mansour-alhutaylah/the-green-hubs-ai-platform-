"""Tenant-safe request-hash computation for analysis-run idempotency.

Mandatory Correction 1 (Sprint 3.6B): the hash is computed over every
behavior-changing input, including ``organization_id`` itself, so that
two organizations issuing byte-identical requests never collide --
``UNIQUE(organization_id, request_hash)`` (migration ``da0298a9c722``)
is a declarative backstop on top of this, not a substitute for it.

Fields are joined with ``\\x1f`` (ASCII unit separator) before hashing
so that no ambiguous concatenation of adjacent variable-length fields
(e.g. two UUIDs) can collide -- a fixed delimiter guaranteed never to
appear in any of the inputs themselves.

Callers must convert numeric settings (temperature, minimum_relevance_score)
to ``Decimal`` the same way on every call (e.g. always ``Decimal(str(x))``
from the same source float) -- ``Decimal("0.10")`` and ``Decimal("0.1")``
hash differently despite being numerically equal, since this function
hashes their ``str()`` form, not their numeric value.
"""

import hashlib
import re
from decimal import Decimal
from uuid import UUID

_WHITESPACE_RE = re.compile(r"\s+")
_FIELD_SEPARATOR = "\x1f"


def normalize_query_text(query_text: str) -> str:
    return _WHITESPACE_RE.sub(" ", query_text.strip())


def compute_request_hash(
    *,
    organization_id: UUID,
    engagement_id: UUID,
    document_id: UUID | None,
    evidence_revision: str,
    analysis_type: str,
    query_text: str,
    provider: str,
    model: str,
    prompt_template_version: str,
    output_schema_version: str,
    temperature: Decimal,
    retrieval_top_k: int,
    embedding_provider: str,
    embedding_model: str,
    embedding_model_version: str,
    minimum_relevance_score: Decimal,
) -> str:
    parts = [
        str(organization_id),
        str(engagement_id),
        str(document_id) if document_id is not None else "",
        evidence_revision,
        analysis_type,
        normalize_query_text(query_text),
        provider,
        model,
        prompt_template_version,
        output_schema_version,
        str(temperature),
        str(retrieval_top_k),
        embedding_provider,
        embedding_model,
        embedding_model_version,
        str(minimum_relevance_score),
    ]
    payload = _FIELD_SEPARATOR.join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
