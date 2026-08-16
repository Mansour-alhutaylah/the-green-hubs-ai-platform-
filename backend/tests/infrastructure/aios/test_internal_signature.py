"""The Python half of the cross-language signing parity gate.

Every expected value comes from
``tests/fixtures/aios_signature_vectors.json`` -- the same file the
Node test reads. Nothing is restated here. Two independently maintained
copies of an expected signature will drift, and once they have, each
suite agrees with itself while the two languages disagree on the wire:
exactly the failure this gate exists to catch.
"""

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from app.domain.aios.contracts import AIOSErrorCategory
from app.infrastructure.aios.internal_signature import (
    DEFAULT_MAX_CLOCK_SKEW_SECONDS,
    HEADER_KEY_ID,
    HEADER_REQUEST_ID,
    HEADER_SIGNATURE,
    HEADER_TIMESTAMP,
    SignatureError,
    SigningKeyRing,
    body_digest,
    build_key_ring,
    build_signature_headers,
    canonical_string,
    decode_body_base64,
    format_timestamp,
    is_valid_key_id,
    parse_timestamp,
    sign_canonical,
    verify_signed_request,
)

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "aios_signature_vectors.json"

_FIXTURE: dict[str, Any] = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
SECRET: str = _FIXTURE["secret_utf8"]
VECTORS: list[dict[str, Any]] = _FIXTURE["vectors"]

_VECTOR_IDS = [vector["name"] for vector in VECTORS]


def _body_bytes(vector: dict[str, Any]) -> bytes:
    """The exact bytes, via the same base64 hop the orchestrator uses."""

    encoded = base64.b64encode(vector["body_utf8"].encode("utf-8")).decode("ascii")
    return base64.b64decode(encoded, validate=True)


def _key_ring(vector: dict[str, Any]) -> SigningKeyRing:
    return SigningKeyRing(keys={vector["key_id"]: SECRET}, active_key_id=vector["key_id"])


def _signed_at(vector: dict[str, Any]) -> datetime:
    return parse_timestamp(vector["timestamp"])


# ---------------------------------------------------------------------------
# The fixture itself must be worth trusting
# ---------------------------------------------------------------------------


def test_the_fixture_exists_and_is_not_trivial() -> None:
    assert FIXTURE_PATH.is_file()
    assert _FIXTURE["algorithm"] == "HMAC-SHA256"
    assert _FIXTURE["canonical_separator"] == "\n"
    assert len(VECTORS) >= 4


def test_the_fixture_contains_a_non_ascii_vector() -> None:
    """A fixture of only ASCII vectors passes under a wrong encoding path.

    Python's ``json.dumps`` escapes non-ASCII to ``\\uXXXX`` by default,
    so an implementation that re-serialized instead of signing raw bytes
    would still satisfy every ASCII case and fail on the first Arabic
    document title. The non-ASCII vector is the one that catches it.
    """

    assert any(not vector["body_utf8"].isascii() for vector in VECTORS)


# ---------------------------------------------------------------------------
# Parity: every field of every vector
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("vector", VECTORS, ids=_VECTOR_IDS)
def test_body_digest_matches_the_fixture(vector: dict[str, Any]) -> None:
    body = _body_bytes(vector)
    assert len(body) == vector["body_byte_length"]
    assert body_digest(body) == vector["body_sha256_hex"]


@pytest.mark.parametrize("vector", VECTORS, ids=_VECTOR_IDS)
def test_canonical_bytes_match_the_fixture(vector: dict[str, Any]) -> None:
    canonical = canonical_string(
        key_id=vector["key_id"],
        timestamp=vector["timestamp"],
        request_id=vector["request_id"],
        workflow=vector["workflow"],
        body=_body_bytes(vector),
    )
    assert len(canonical) == vector["canonical_byte_length"]
    assert canonical.decode("utf-8") == vector["canonical_string_utf8"]
    assert not canonical.endswith(b"\n"), "no trailing newline"
    assert b"\r" not in canonical, "LF only, never CRLF"


@pytest.mark.parametrize("vector", VECTORS, ids=_VECTOR_IDS)
def test_signature_matches_the_fixture(vector: dict[str, Any]) -> None:
    signature = sign_canonical(
        SECRET,
        canonical_string(
            key_id=vector["key_id"],
            timestamp=vector["timestamp"],
            request_id=vector["request_id"],
            workflow=vector["workflow"],
            body=_body_bytes(vector),
        ),
    )
    assert signature == vector["signature_hex"]
    assert f"sha256={signature}" == vector["signature_header_value"]


@pytest.mark.parametrize("vector", VECTORS, ids=_VECTOR_IDS)
def test_a_valid_signature_verifies(vector: dict[str, Any]) -> None:
    request_id = verify_signed_request(
        key_ring=_key_ring(vector),
        key_id=vector["key_id"],
        timestamp=vector["timestamp"],
        request_id=vector["request_id"],
        workflow=vector["workflow"],
        signature=vector["signature_header_value"],
        body=_body_bytes(vector),
        now=_signed_at(vector),
    )
    assert request_id == UUID(vector["request_id"])


@pytest.mark.parametrize("vector", VECTORS, ids=_VECTOR_IDS)
def test_the_non_ascii_body_survives_the_base64_hop(vector: dict[str, Any]) -> None:
    assert _body_bytes(vector).decode("utf-8") == vector["body_utf8"]


def test_reserialising_a_parsed_body_changes_the_digest() -> None:
    """The concrete reason raw-body capture is mandatory.

    Asserts the hazard is real rather than theoretical: Python's default
    ``json.dumps`` of the parsed non-ASCII body produces different bytes,
    and therefore a different digest, from the bytes that were signed.
    """

    vector = next(v for v in VECTORS if not v["body_utf8"].isascii())
    exact = _body_bytes(vector)
    reserialised = json.dumps(json.loads(vector["body_utf8"])).encode("utf-8")

    assert body_digest(exact) == vector["body_sha256_hex"]
    assert reserialised != exact
    assert body_digest(reserialised) != vector["body_sha256_hex"]


# ---------------------------------------------------------------------------
# Every tamper case is refused
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("vector", VECTORS, ids=_VECTOR_IDS)
def test_a_changed_body_fails(vector: dict[str, Any]) -> None:
    with pytest.raises(SignatureError) as caught:
        verify_signed_request(
            key_ring=_key_ring(vector),
            key_id=vector["key_id"],
            timestamp=vector["timestamp"],
            request_id=vector["request_id"],
            workflow=vector["workflow"],
            signature=vector["signature_header_value"],
            body=_body_bytes(vector) + b" ",
            now=_signed_at(vector),
        )
    assert caught.value.category is AIOSErrorCategory.SIGNATURE_INVALID


@pytest.mark.parametrize("vector", VECTORS, ids=_VECTOR_IDS)
def test_a_changed_workflow_fails(vector: dict[str, Any]) -> None:
    """A signature is bound to one workflow and cannot be replayed at another."""

    with pytest.raises(SignatureError):
        verify_signed_request(
            key_ring=_key_ring(vector),
            key_id=vector["key_id"],
            timestamp=vector["timestamp"],
            request_id=vector["request_id"],
            workflow="hafidh.master_inbox",
            signature=vector["signature_header_value"],
            body=_body_bytes(vector),
            now=_signed_at(vector),
        )


@pytest.mark.parametrize("vector", VECTORS, ids=_VECTOR_IDS)
def test_a_changed_request_id_fails(vector: dict[str, Any]) -> None:
    with pytest.raises(SignatureError):
        verify_signed_request(
            key_ring=_key_ring(vector),
            key_id=vector["key_id"],
            timestamp=vector["timestamp"],
            request_id="11111111-2222-4333-8444-555555555555",
            workflow=vector["workflow"],
            signature=vector["signature_header_value"],
            body=_body_bytes(vector),
            now=_signed_at(vector),
        )


def test_an_unknown_key_id_fails() -> None:
    vector = VECTORS[0]
    with pytest.raises(SignatureError) as caught:
        verify_signed_request(
            key_ring=_key_ring(vector),
            key_id="gh-aios-f2n-dev-999",
            timestamp=vector["timestamp"],
            request_id=vector["request_id"],
            workflow=vector["workflow"],
            signature=vector["signature_header_value"],
            body=_body_bytes(vector),
            now=_signed_at(vector),
        )
    assert caught.value.category is AIOSErrorCategory.UNSUPPORTED_KEY_ID


@pytest.mark.parametrize(
    "malformed",
    ["", "sha256=", "sha256=abc", "deadbeef", "sha256=" + "Z" * 64, None, 12345],
)
def test_a_malformed_signature_fails_safely(malformed: object) -> None:
    """Never a crash, never a 500 -- always a refusal."""

    vector = VECTORS[0]
    with pytest.raises(SignatureError):
        verify_signed_request(
            key_ring=_key_ring(vector),
            key_id=vector["key_id"],
            timestamp=vector["timestamp"],
            request_id=vector["request_id"],
            workflow=vector["workflow"],
            signature=malformed,
            body=_body_bytes(vector),
            now=_signed_at(vector),
        )


@pytest.mark.parametrize("offset_seconds", [301, -301, 3600, -3600])
def test_a_timestamp_outside_the_window_fails(offset_seconds: int) -> None:
    """Two-sided: a future-dated timestamp is refused under the same bound."""

    vector = VECTORS[0]
    with pytest.raises(SignatureError) as caught:
        verify_signed_request(
            key_ring=_key_ring(vector),
            key_id=vector["key_id"],
            timestamp=vector["timestamp"],
            request_id=vector["request_id"],
            workflow=vector["workflow"],
            signature=vector["signature_header_value"],
            body=_body_bytes(vector),
            now=_signed_at(vector) + timedelta(seconds=offset_seconds),
        )
    assert caught.value.category is AIOSErrorCategory.TIMESTAMP_OUT_OF_WINDOW


@pytest.mark.parametrize("offset_seconds", [0, 299, -299, 300, -300])
def test_a_timestamp_inside_the_window_is_accepted(offset_seconds: int) -> None:
    vector = VECTORS[0]
    verify_signed_request(
        key_ring=_key_ring(vector),
        key_id=vector["key_id"],
        timestamp=vector["timestamp"],
        request_id=vector["request_id"],
        workflow=vector["workflow"],
        signature=vector["signature_header_value"],
        body=_body_bytes(vector),
        now=_signed_at(vector) + timedelta(seconds=offset_seconds),
    )


def test_the_default_window_is_the_specified_five_minutes() -> None:
    assert DEFAULT_MAX_CLOCK_SKEW_SECONDS == 300


# ---------------------------------------------------------------------------
# Timestamp format: exactly one accepted spelling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "2026-08-12T14:47:05.123Z",  # fractional seconds
        "2026-08-12T14:47:05+00:00",  # numeric offset
        "2026-08-12T14:47:05",  # no zone
        "2026-08-12 14:47:05Z",  # space separator
        "not-a-timestamp",
        "",
        None,
        1754999225,
    ],
)
def test_a_non_canonical_timestamp_is_refused(raw: object) -> None:
    """One spelling only -- the string that was signed is the string
    that must be re-derived."""

    with pytest.raises(SignatureError):
        parse_timestamp(raw)


def test_format_timestamp_round_trips() -> None:
    moment = datetime(2026, 8, 12, 14, 47, 5, tzinfo=timezone.utc)
    assert format_timestamp(moment) == "2026-08-12T14:47:05Z"
    assert parse_timestamp(format_timestamp(moment)) == moment


def test_format_timestamp_normalises_a_non_utc_input() -> None:
    moment = datetime(2026, 8, 12, 17, 47, 5, tzinfo=timezone(timedelta(hours=3)))
    assert format_timestamp(moment) == "2026-08-12T14:47:05Z"


# ---------------------------------------------------------------------------
# Request id: canonical UUID form only
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "550E8400-E29B-41D4-A716-446655440000",  # uppercase
        "550e8400e29b41d4a716446655440000",  # unhyphenated
        "not-a-uuid",
        "",
        None,
    ],
)
def test_a_non_canonical_request_id_is_refused(raw: object) -> None:
    vector = VECTORS[0]
    with pytest.raises(SignatureError):
        verify_signed_request(
            key_ring=_key_ring(vector),
            key_id=vector["key_id"],
            timestamp=vector["timestamp"],
            request_id=raw,
            workflow=vector["workflow"],
            signature=vector["signature_header_value"],
            body=_body_bytes(vector),
            now=_signed_at(vector),
        )


# ---------------------------------------------------------------------------
# Key ring, rotation overlap, and key-id hygiene
# ---------------------------------------------------------------------------


def test_rotation_overlap_accepts_both_keys() -> None:
    """The property that makes rotation an overlap rather than an outage."""

    old_key, new_key = "gh-aios-f2n-dev-001", "gh-aios-f2n-dev-002"
    ring = SigningKeyRing(
        keys={old_key: SECRET, new_key: "a-different-secret"}, active_key_id=new_key
    )
    body = b'{"probe":true}'
    request_id = UUID("550e8400-e29b-41d4-a716-446655440000")
    now = datetime(2026, 8, 12, 14, 47, 5, tzinfo=timezone.utc)

    # Signed under the OLD key while the signer has already moved on.
    old_canonical = canonical_string(
        key_id=old_key,
        timestamp=format_timestamp(now),
        request_id=str(request_id),
        workflow="nora.health_check",
        body=body,
    )
    verify_signed_request(
        key_ring=ring,
        key_id=old_key,
        timestamp=format_timestamp(now),
        request_id=str(request_id),
        workflow="nora.health_check",
        signature=f"sha256={sign_canonical(SECRET, old_canonical)}",
        body=body,
        now=now,
    )

    # And the new key verifies too, under its own distinct secret.
    headers = build_signature_headers(
        key_ring=ring,
        workflow="nora.health_check",
        request_id=request_id,
        body=body,
        now=now,
    )
    assert headers[HEADER_KEY_ID] == new_key
    verify_signed_request(
        key_ring=ring,
        key_id=headers[HEADER_KEY_ID],
        timestamp=headers[HEADER_TIMESTAMP],
        request_id=headers[HEADER_REQUEST_ID],
        workflow="nora.health_check",
        signature=headers[HEADER_SIGNATURE],
        body=body,
        now=now,
    )


def test_a_retired_key_stops_verifying_once_removed() -> None:
    """Removal is the step that makes retirement real."""

    old_key, new_key = "gh-aios-f2n-dev-001", "gh-aios-f2n-dev-002"
    body = b"{}"
    now = datetime(2026, 8, 12, 14, 47, 5, tzinfo=timezone.utc)
    request_id = "550e8400-e29b-41d4-a716-446655440000"
    signature = sign_canonical(
        SECRET,
        canonical_string(
            key_id=old_key,
            timestamp=format_timestamp(now),
            request_id=request_id,
            workflow="nora.health_check",
            body=body,
        ),
    )

    after_rotation = SigningKeyRing(keys={new_key: SECRET}, active_key_id=new_key)
    with pytest.raises(SignatureError) as caught:
        verify_signed_request(
            key_ring=after_rotation,
            key_id=old_key,
            timestamp=format_timestamp(now),
            request_id=request_id,
            workflow="nora.health_check",
            signature=f"sha256={signature}",
            body=body,
            now=now,
        )
    assert caught.value.category is AIOSErrorCategory.UNSUPPORTED_KEY_ID


def test_a_dev_key_is_absent_from_a_prod_ring() -> None:
    """Environment separation is structural, not procedural: the key id
    encodes the environment, so a dev key is simply not in the ring."""

    prod = SigningKeyRing(
        keys={"gh-aios-f2n-prod-001": SECRET}, active_key_id="gh-aios-f2n-prod-001"
    )
    assert prod.secret_for("gh-aios-f2n-dev-001") is None


@pytest.mark.parametrize(
    "key_id", ["gh-aios-f2n-dev-001", "gh-aios-n2f-prod-042", "a", "0" * 64]
)
def test_well_formed_key_ids_are_accepted(key_id: str) -> None:
    assert is_valid_key_id(key_id)


@pytest.mark.parametrize(
    "key_id",
    ["", "GH-AIOS-F2N-DEV-001", "gh aios", "gh_aios", "x" * 65, "gh-aios/../etc", None, 7],
)
def test_malformed_key_ids_are_refused(key_id: object) -> None:
    assert not is_valid_key_id(key_id)


def test_a_key_ring_rejects_an_active_id_it_does_not_hold() -> None:
    with pytest.raises(ValueError):
        SigningKeyRing(keys={"gh-aios-f2n-dev-001": SECRET}, active_key_id="gh-aios-f2n-dev-002")


def test_a_key_ring_rejects_an_empty_secret() -> None:
    with pytest.raises(ValueError):
        SigningKeyRing(keys={"gh-aios-f2n-dev-001": ""}, active_key_id="gh-aios-f2n-dev-001")


def test_a_key_ring_rejects_a_malformed_key_id() -> None:
    with pytest.raises(ValueError):
        SigningKeyRing(keys={"NOT VALID": SECRET}, active_key_id="NOT VALID")


def test_build_key_ring_returns_none_when_unconfigured() -> None:
    """The app must still import and boot without AIOS credentials."""

    assert build_key_ring(None, None) is None
    assert build_key_ring({}, "gh-aios-f2n-dev-001") is None
    assert build_key_ring({"gh-aios-f2n-dev-001": SECRET}, None) is None


def test_build_key_ring_still_raises_on_a_malformed_configuration() -> None:
    """Silence here would mean booting with a key ring nobody meant to have."""

    with pytest.raises(ValueError):
        build_key_ring({"bad id": SECRET}, "bad id")


# ---------------------------------------------------------------------------
# Signing headers, and the round trip
# ---------------------------------------------------------------------------


def test_build_signature_headers_round_trips_through_verification() -> None:
    ring = SigningKeyRing(
        keys={"gh-aios-f2n-dev-001": SECRET}, active_key_id="gh-aios-f2n-dev-001"
    )
    body = '{"note":"المركز الأخضر"}'.encode("utf-8")
    request_id = UUID("7c9e6679-7425-40de-944b-e07fc1f90ae7")
    now = datetime(2026, 8, 12, 14, 47, 5, tzinfo=timezone.utc)

    headers = build_signature_headers(
        key_ring=ring,
        workflow="nora.health_check",
        request_id=request_id,
        body=body,
        now=now,
    )

    assert set(headers) == {
        HEADER_KEY_ID,
        HEADER_TIMESTAMP,
        HEADER_REQUEST_ID,
        HEADER_SIGNATURE,
    }
    assert headers[HEADER_SIGNATURE].startswith("sha256=")
    assert len(headers[HEADER_SIGNATURE]) == len("sha256=") + 64

    assert (
        verify_signed_request(
            key_ring=ring,
            key_id=headers[HEADER_KEY_ID],
            timestamp=headers[HEADER_TIMESTAMP],
            request_id=headers[HEADER_REQUEST_ID],
            workflow="nora.health_check",
            signature=headers[HEADER_SIGNATURE],
            body=body,
            now=now,
        )
        == request_id
    )


def test_header_names_are_the_specified_ones() -> None:
    """Pinned: n8n lowercases header names, and both sides look up the
    lowercase form. A rename here silently breaks the orchestrator."""

    assert HEADER_KEY_ID == "X-GH-AIOS-Key-Id"
    assert HEADER_TIMESTAMP == "X-GH-AIOS-Timestamp"
    assert HEADER_REQUEST_ID == "X-GH-Request-Id"
    assert HEADER_SIGNATURE == "X-GH-AIOS-Signature"


# ---------------------------------------------------------------------------
# Base64 body transport
# ---------------------------------------------------------------------------


def test_decode_body_base64_round_trips_exact_bytes() -> None:
    body = '{"note":"المركز الأخضر — GH"}'.encode("utf-8")
    encoded = base64.b64encode(body).decode("ascii")
    assert decode_body_base64(encoded, max_bytes=1024) == body


@pytest.mark.parametrize("raw", ["not base64!!", "a", None, 7, "e30=====" ])
def test_decode_body_base64_refuses_malformed_input(raw: object) -> None:
    """Strict validation: a lenient decoder silently ignores characters
    outside the alphabet, so two transport strings could decode to the
    same bytes."""

    with pytest.raises(SignatureError):
        decode_body_base64(raw, max_bytes=1024)


def test_decode_body_base64_enforces_the_size_ceiling() -> None:
    oversized = base64.b64encode(b"x" * 4096).decode("ascii")
    with pytest.raises(SignatureError) as caught:
        decode_body_base64(oversized, max_bytes=64)
    assert caught.value.category is AIOSErrorCategory.PAYLOAD_TOO_LARGE


def test_an_empty_body_is_not_a_special_case() -> None:
    assert body_digest(b"") == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    assert decode_body_base64("", max_bytes=1024) == b""


# ---------------------------------------------------------------------------
# The key-ring lookup must not become a timing oracle
# ---------------------------------------------------------------------------


def test_an_unknown_key_id_still_performs_the_full_hmac(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The response shape for "no such key" and "wrong signature" is
    already identical. This closes the timing channel behind it: an early
    return on an unknown key id would let an attacker measure the
    difference and enumerate which key ids exist.

    Asserted by counting the HMAC computations, not by timing -- a timing
    assertion would be flaky, and the property that matters is that the
    same work happens on both paths.
    """

    from app.infrastructure.aios import internal_signature as module

    calls: list[int] = []
    real_sign = module.sign_canonical

    def counting_sign(secret: str, canonical: bytes) -> str:
        calls.append(1)
        return real_sign(secret, canonical)

    monkeypatch.setattr(module, "sign_canonical", counting_sign)

    vector = VECTORS[0]
    ring = _key_ring(vector)

    # A known key with a bad signature: one HMAC.
    with pytest.raises(SignatureError):
        module.verify_signed_request(
            key_ring=ring,
            key_id=vector["key_id"],
            timestamp=vector["timestamp"],
            request_id=vector["request_id"],
            workflow=vector["workflow"],
            signature="sha256=" + "0" * 64,
            body=_body_bytes(vector),
            now=_signed_at(vector),
        )
    known_key_calls = len(calls)

    calls.clear()

    # An unknown key id: the same one HMAC, against a decoy secret.
    with pytest.raises(SignatureError):
        module.verify_signed_request(
            key_ring=ring,
            key_id="gh-aios-f2n-dev-999",
            timestamp=vector["timestamp"],
            request_id=vector["request_id"],
            workflow=vector["workflow"],
            signature=vector["signature_header_value"],
            body=_body_bytes(vector),
            now=_signed_at(vector),
        )

    assert known_key_calls == 1
    assert len(calls) == known_key_calls, (
        "an unknown key id short-circuited before the HMAC, which distinguishes "
        "'no such key' from 'wrong signature' by timing"
    )


def test_the_decoy_secret_is_generated_per_process_not_hardcoded() -> None:
    """It must never coincide with a real secret, and must never be a
    value an attacker could look up in source."""

    from app.infrastructure.aios.internal_signature import _DECOY_SECRET

    assert len(_DECOY_SECRET) == 64
    assert _DECOY_SECRET != SECRET


def test_a_decoy_signature_can_never_be_accepted() -> None:
    """Even if an attacker somehow produced the decoy's signature, the
    unknown-key branch raises regardless of whether the comparison
    matched."""

    from app.infrastructure.aios import internal_signature as module

    vector = VECTORS[0]
    decoy_signature = module.sign_canonical(
        module._DECOY_SECRET,
        module.canonical_string(
            key_id="gh-aios-f2n-dev-999",
            timestamp=vector["timestamp"],
            request_id=vector["request_id"],
            workflow=vector["workflow"],
            body=_body_bytes(vector),
        ),
    )

    with pytest.raises(SignatureError) as caught:
        module.verify_signed_request(
            key_ring=_key_ring(vector),
            key_id="gh-aios-f2n-dev-999",
            timestamp=vector["timestamp"],
            request_id=vector["request_id"],
            workflow=vector["workflow"],
            signature=f"sha256={decoy_signature}",
            body=_body_bytes(vector),
            now=_signed_at(vector),
        )
    assert caught.value.category is AIOSErrorCategory.UNSUPPORTED_KEY_ID
