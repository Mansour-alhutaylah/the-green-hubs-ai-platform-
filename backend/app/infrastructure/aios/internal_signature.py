"""HMAC-SHA256 request signing between this application and n8n Cloud.

The normative specification is
``project-governance/07-aios/AIOS_Internal_Signing_Protocol.md``; this
module is its only implementation, and
``tests/fixtures/aios_signature_vectors.json`` is the fixture both this
module and the reviewed n8n-side JavaScript are proved against. Change
the canonical string here and the cross-language parity test fails --
which is the point.

**Why a signature and not a shared bearer header.** n8n's Webhook node
offers Header Auth: a static value compared for equality. That proves
nothing about the request body, is fully replayable, and is entirely
compromised by a single log capture. It is not a signature and must
never be described as one. Header Auth may sit in front of this as a
coarse pre-filter for internet noise; the trust decision is here.

**Where the secret lives.** The target is n8n Cloud, where a Code node
cannot read credential values and ``$env`` is unavailable. Founder
decision (Gate 1) therefore forbids putting the secret in n8n at all --
including in ``$vars`` and including in an exported workflow's JSON.
Instead the orchestrator forwards the received headers and the exact raw
body back to this application's verification endpoint, and *this*
process performs the comparison. The secret never leaves the platform
secret store. See ``app.services.aios.request_verification``.

**The canonical string**, five fields, LF-separated, no trailing
newline, every component UTF-8::

    key_id     \\n
    timestamp  \\n
    request_id \\n
    workflow   \\n
    sha256_hex(exact request body bytes)

    signature = hex(HMAC-SHA256(secret_utf8, canonical_utf8))

``correlation_id`` is deliberately *not* signed. It is diagnostic, the
request-context middleware may legitimately replace a malformed inbound
value with a fresh one, and binding it would produce signature failures
with no security benefit. Its transmitted value is covered anyway,
because it also appears inside the signed body.

**Never re-serialize.** The digest is over the bytes that are actually
transmitted, computed once. A parsed object serialized again is not
guaranteed to produce identical bytes across languages -- Python's
``json.dumps`` escapes non-ASCII to ``\\uXXXX`` by default, so an Arabic
payload yields a completely different digest from JavaScript's
``JSON.stringify`` while every ASCII test still passes. That failure
ships silently. Hence :func:`body_digest` takes ``bytes``, and callers
must transmit exactly what they signed.
"""

import base64
import binascii
import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final, Mapping
from uuid import UUID

from app.domain.aios.contracts import AIOSErrorCategory

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Wire constants. These are protocol, not configuration: a deployment that
# could change them by environment variable could be misconfigured into a
# weaker scheme, which is the same mistake `SupabaseJWTVerifier` avoids by
# hardcoding its algorithm allow-list.
# --------------------------------------------------------------------------

HEADER_KEY_ID: Final = "X-GH-AIOS-Key-Id"
HEADER_TIMESTAMP: Final = "X-GH-AIOS-Timestamp"
HEADER_REQUEST_ID: Final = "X-GH-Request-Id"
HEADER_SIGNATURE: Final = "X-GH-AIOS-Signature"

#: HTTP header names are case-insensitive and n8n normalizes them to
#: lowercase. A verifier written against the mixed-case spelling reads
#: ``undefined`` and fails every request -- a failure that looks like a
#: signing bug and is not. Both sides look up the lowercase form.
HEADER_KEY_ID_LOWER: Final = HEADER_KEY_ID.lower()
HEADER_TIMESTAMP_LOWER: Final = HEADER_TIMESTAMP.lower()
HEADER_REQUEST_ID_LOWER: Final = HEADER_REQUEST_ID.lower()
HEADER_SIGNATURE_LOWER: Final = HEADER_SIGNATURE.lower()

#: Single LF (0x0A). Never CRLF, and there is no trailing separator.
CANONICAL_SEPARATOR: Final = "\n"
SIGNATURE_PREFIX: Final = "sha256="
#: SHA-256 hex digest length; also the exact length of a signature hex.
DIGEST_HEX_LENGTH: Final = 64
#: ``YYYY-MM-DDTHH:MM:SSZ`` -- UTC, second precision, literal ``Z``. No
#: fractional seconds and no numeric offset: one accepted spelling means
#: the bytes that were signed are the bytes that are re-derived.
TIMESTAMP_FORMAT: Final = "%Y-%m-%dT%H:%M:%SZ"
#: Two-sided. A future-dated timestamp is rejected under the same bound,
#: not tolerated -- a one-sided window lets a signer with a fast clock
#: mint long-lived signatures.
DEFAULT_MAX_CLOCK_SKEW_SECONDS: Final = 300

_KEY_ID_MAX_LENGTH: Final = 64
_KEY_ID_ALLOWED_CHARACTERS: Final = frozenset(
    "abcdefghijklmnopqrstuvwxyz0123456789-"
)

#: Used only to keep the verification path's work constant when a key id
#: is not in the ring -- see :func:`verify_signed_request`. Generated per
#: process rather than hardcoded so it can never coincide with a real
#: secret, and never compared for equality with anything that matters.
_DECOY_SECRET: Final = secrets.token_hex(32)


class SignatureError(Exception):
    """A request failed verification.

    Carries a :class:`AIOSErrorCategory` for *logging only*. Callers must
    not surface it: the verification endpoint answers every failure with
    one generic category, so that it cannot be used as an oracle for
    which key ids exist or whether a timestamp merely expired.
    """

    def __init__(self, category: AIOSErrorCategory, detail: str) -> None:
        self.category = category
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class SigningKeyRing:
    """The key ids this process will sign with and accept.

    Rotation is an overlap, never a cutover. The verifier accepts every
    key in :attr:`keys`; the signer uses only :attr:`active_key_id`. A
    rotation is therefore: add the new key (both verify) -> switch the
    active id -> observe -> remove the old key. A retired key that still
    verifies is not retired, so the removal step is not optional.

    The key id encodes direction and environment
    (``gh-aios-<f2n|n2f>-<dev|prod>-<serial>``), so a development key
    presented to a production verifier is not merely wrong -- it is
    absent from that verifier's ring entirely and fails structurally.
    That is what makes the dev/prod separation self-enforcing rather
    than procedural.
    """

    keys: Mapping[str, str]
    active_key_id: str

    def __post_init__(self) -> None:
        if not self.keys:
            raise ValueError("A signing key ring must contain at least one key")
        for key_id, secret in self.keys.items():
            if not is_valid_key_id(key_id):
                raise ValueError(f"Malformed AIOS signing key id: {key_id!r}")
            if not secret:
                raise ValueError(f"AIOS signing key {key_id!r} has an empty secret")
        if self.active_key_id not in self.keys:
            raise ValueError(
                "The active AIOS signing key id is not present in the key ring"
            )

    def secret_for(self, key_id: str) -> str | None:
        """The secret registered for ``key_id``, or ``None`` if unknown."""

        return self.keys.get(key_id)

    @property
    def active_secret(self) -> str:
        return self.keys[self.active_key_id]


def is_valid_key_id(key_id: object) -> bool:
    """Whether ``key_id`` is a well-formed key identifier."""

    return (
        isinstance(key_id, str)
        and 0 < len(key_id) <= _KEY_ID_MAX_LENGTH
        and set(key_id) <= _KEY_ID_ALLOWED_CHARACTERS
    )


def body_digest(body: bytes) -> str:
    """Lowercase hex SHA-256 of the exact request body bytes.

    An empty body is not a special case: it digests to the SHA-256 of
    zero bytes and is signed like any other.
    """

    return hashlib.sha256(body).hexdigest()


def canonical_string(
    *, key_id: str, timestamp: str, request_id: str, workflow: str, body: bytes
) -> bytes:
    """Build the exact bytes that are signed.

    Returns UTF-8 bytes of the five LF-separated fields, with no
    trailing newline.
    """

    return CANONICAL_SEPARATOR.join(
        (key_id, timestamp, request_id, workflow, body_digest(body))
    ).encode("utf-8")


def sign_canonical(secret: str, canonical: bytes) -> str:
    """Lowercase hex HMAC-SHA256 over ``canonical`` under ``secret``."""

    return hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()


def format_timestamp(moment: datetime) -> str:
    """Render ``moment`` in the one accepted timestamp spelling."""

    return moment.astimezone(timezone.utc).strftime(TIMESTAMP_FORMAT)


def parse_timestamp(raw: object) -> datetime:
    """Parse a signing timestamp strictly, or raise.

    Strict on purpose. ``datetime.fromisoformat`` would accept
    fractional seconds and numeric offsets, which means two spellings of
    the same instant -- and only one of them is the string that was
    signed.
    """

    if not isinstance(raw, str):
        raise SignatureError(
            AIOSErrorCategory.CONTRACT_INVALID, "timestamp header is not a string"
        )
    try:
        parsed = datetime.strptime(raw, TIMESTAMP_FORMAT)
    except ValueError as exc:
        raise SignatureError(
            AIOSErrorCategory.CONTRACT_INVALID, "timestamp header is malformed"
        ) from exc
    return parsed.replace(tzinfo=timezone.utc)


def build_signature_headers(
    *,
    key_ring: SigningKeyRing,
    workflow: str,
    request_id: UUID,
    body: bytes,
    now: datetime,
) -> dict[str, str]:
    """Produce the four signing headers for an outbound request.

    ``body`` must be the exact bytes the caller will transmit. Passing a
    re-serialized copy produces a valid signature over the wrong bytes,
    and the receiver rejects every such request.
    """

    timestamp = format_timestamp(now)
    canonical = canonical_string(
        key_id=key_ring.active_key_id,
        timestamp=timestamp,
        request_id=str(request_id),
        workflow=workflow,
        body=body,
    )
    signature = sign_canonical(key_ring.active_secret, canonical)
    return {
        HEADER_KEY_ID: key_ring.active_key_id,
        HEADER_TIMESTAMP: timestamp,
        HEADER_REQUEST_ID: str(request_id),
        HEADER_SIGNATURE: f"{SIGNATURE_PREFIX}{signature}",
    }


def _parse_signature_header(raw: object) -> str:
    """Extract the hex digest from a ``sha256=<hex>`` header value."""

    if not isinstance(raw, str) or not raw.startswith(SIGNATURE_PREFIX):
        raise SignatureError(
            AIOSErrorCategory.SIGNATURE_INVALID, "signature header is malformed"
        )
    candidate = raw[len(SIGNATURE_PREFIX) :]
    # Length and alphabet are checked before the comparison, not to save
    # work but because `hmac.compare_digest` on differing lengths is a
    # comparison that was never going to succeed -- rejecting here keeps
    # the constant-time path operating on two equal-length hex strings.
    if len(candidate) != DIGEST_HEX_LENGTH:
        raise SignatureError(
            AIOSErrorCategory.SIGNATURE_INVALID, "signature has the wrong length"
        )
    if any(character not in "0123456789abcdef" for character in candidate):
        raise SignatureError(
            AIOSErrorCategory.SIGNATURE_INVALID, "signature is not lowercase hex"
        )
    return candidate


def decode_body_base64(raw: object, *, max_bytes: int) -> bytes:
    """Decode the exact body bytes from their base64 transport form.

    The orchestrator cannot forward raw bytes through a JSON field, so
    it forwards them base64-encoded. Validation is strict
    (``validate=True``): a lenient decoder silently ignores characters
    outside the alphabet, which would let two different transport
    strings decode to the same bytes.
    """

    if not isinstance(raw, str):
        raise SignatureError(
            AIOSErrorCategory.CONTRACT_INVALID, "body_base64 is not a string"
        )
    # 4 base64 characters encode 3 bytes; bound the input before decoding
    # so an oversized payload is refused rather than expanded in memory.
    if len(raw) > (max_bytes // 3 + 1) * 4 + 4:
        raise SignatureError(
            AIOSErrorCategory.PAYLOAD_TOO_LARGE, "body_base64 exceeds the size limit"
        )
    try:
        decoded = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SignatureError(
            AIOSErrorCategory.CONTRACT_INVALID, "body_base64 is not valid base64"
        ) from exc
    if len(decoded) > max_bytes:
        raise SignatureError(
            AIOSErrorCategory.PAYLOAD_TOO_LARGE, "request body exceeds the size limit"
        )
    return decoded


def verify_signed_request(
    *,
    key_ring: SigningKeyRing,
    key_id: object,
    timestamp: object,
    request_id: object,
    workflow: str,
    signature: object,
    body: bytes,
    now: datetime,
    max_clock_skew_seconds: int = DEFAULT_MAX_CLOCK_SKEW_SECONDS,
) -> UUID:
    """Verify one signed request, returning its request id.

    Raises :class:`SignatureError` on any failure. The order below is
    deliberate: everything cheap and structural is checked before the
    HMAC is computed, so a malformed request never causes key material
    to be exercised. The one exception is the key-ring lookup, which
    deliberately does *not* short-circuit -- see the comment there.

    Returns:
        The validated ``request_id``.
    """

    if not is_valid_key_id(key_id):
        raise SignatureError(
            AIOSErrorCategory.UNSUPPORTED_KEY_ID, "key id is malformed"
        )
    assert isinstance(key_id, str)  # narrowed by is_valid_key_id

    provided_signature = _parse_signature_header(signature)

    if not isinstance(request_id, str):
        raise SignatureError(
            AIOSErrorCategory.CONTRACT_INVALID, "request id header is not a string"
        )
    try:
        parsed_request_id = UUID(request_id)
    except ValueError as exc:
        raise SignatureError(
            AIOSErrorCategory.CONTRACT_INVALID, "request id header is not a UUID"
        ) from exc
    # The canonical string contains the header verbatim, so a value that
    # is a UUID but not in canonical lowercase-hyphenated form would sign
    # one spelling and be re-derived as another.
    if request_id != str(parsed_request_id):
        raise SignatureError(
            AIOSErrorCategory.CONTRACT_INVALID,
            "request id header is not in canonical UUID form",
        )

    parsed_timestamp = parse_timestamp(timestamp)
    skew = abs((now - parsed_timestamp).total_seconds())
    if skew > max_clock_skew_seconds:
        raise SignatureError(
            AIOSErrorCategory.TIMESTAMP_OUT_OF_WINDOW,
            "timestamp is outside the acceptance window",
        )

    secret = key_ring.secret_for(key_id)

    # An unknown key id still performs the full HMAC, against a decoy
    # secret, and still runs the constant-time comparison. The response
    # shape for "no such key" and "wrong signature" is already identical
    # -- this closes the timing channel *behind* that shape. Returning
    # early here would let an attacker distinguish the two by measuring
    # how long the answer took, and so enumerate which key ids exist.
    expected = sign_canonical(
        _DECOY_SECRET if secret is None else secret,
        canonical_string(
            key_id=key_id,
            timestamp=str(timestamp),
            request_id=request_id,
            workflow=workflow,
            body=body,
        ),
    )
    matched = hmac.compare_digest(expected, provided_signature)

    if secret is None:
        raise SignatureError(
            AIOSErrorCategory.UNSUPPORTED_KEY_ID, "key id is not in the key ring"
        )
    if not matched:
        raise SignatureError(
            AIOSErrorCategory.SIGNATURE_INVALID, "signature does not match"
        )

    return parsed_request_id


def build_key_ring(
    keys: Mapping[str, str] | None, active_key_id: str | None
) -> SigningKeyRing | None:
    """Build a key ring from configuration, or ``None`` if unconfigured.

    Returns ``None`` rather than raising when nothing is configured, so
    the application still imports and boots without AIOS credentials --
    the same deliberate choice ``get_settings()`` makes about a missing
    ``.env``. A *malformed* configuration still raises: silence there
    would mean starting with a key ring nobody meant to have.
    """

    if not keys or not active_key_id:
        return None
    return SigningKeyRing(keys=dict(keys), active_key_id=active_key_id)


def log_verification_failure(error: SignatureError, *, direction: str) -> None:
    """Record a failed verification safely.

    The category and a fixed detail string are recorded; the signature,
    the key material, the canonical string and the body never are. The
    request context factory already attaches correlation and actor ids to
    every record, so the operator gets a traceable event without this
    module adding anything sensitive to it.
    """

    logger.warning(
        "AIOS signature verification failed direction=%s category=%s detail=%s",
        direction,
        error.category.value,
        error.detail,
    )
