"""Unit tests for Supabase JWT verification -- no network, no database.

All tokens are signed locally with a throwaway EC test keypair generated
per test; the JWKS document a verifier consults is always a fake, injected
``fetch`` callable, never the real project endpoint. No production secret
or private key is ever used or logged.
"""

import base64
import datetime
import json
import uuid

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.infrastructure.security.supabase_jwt import (
    JWKSCache,
    SupabaseJWTVerifier,
    build_verifier_from_settings,
)

ISSUER = "https://test.supabase.co/auth/v1"
AUDIENCE = "authenticated"


def _b64url_uint(value: int) -> str:
    byte_length = (value.bit_length() + 7) // 8 or 1
    raw = value.to_bytes(byte_length, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _generate_keypair():
    private_key = ec.generate_private_key(ec.SECP256R1())
    return private_key, private_key.public_key()


def _public_key_to_jwk(public_key, kid: str) -> dict:
    numbers = public_key.public_numbers()
    return {
        "kty": "EC",
        "crv": "P-256",
        "kid": kid,
        "x": _b64url_uint(numbers.x),
        "y": _b64url_uint(numbers.y),
        "use": "sig",
        "alg": "ES256",
    }


def _make_token(
    private_key,
    *,
    kid: str = "test-kid",
    overrides: dict | None = None,
    omit: list[str] | None = None,
) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(uuid.uuid4()),
        "aud": AUDIENCE,
        "iss": ISSUER,
        "exp": now + datetime.timedelta(hours=1),
        "iat": now,
    }
    if overrides:
        payload.update(overrides)
    for key in omit or []:
        payload.pop(key, None)
    return pyjwt.encode(payload, private_key, algorithm="ES256", headers={"kid": kid})


def _tamper_header(token: str, **overrides: str) -> str:
    header_b64, payload_b64, sig_b64 = token.split(".")
    header = json.loads(base64.urlsafe_b64decode(header_b64 + "=="))
    header.update(overrides)
    new_header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    return f"{new_header_b64}.{payload_b64}.{sig_b64}"


@pytest.fixture
def keypair():
    return _generate_keypair()


@pytest.fixture
def verifier(keypair):
    _private_key, public_key = keypair
    jwk = _public_key_to_jwk(public_key, "test-kid")

    def fake_fetch(_uri: str) -> dict:
        return {"keys": [jwk]}

    cache = JWKSCache("https://unused.example/jwks.json", fetch=fake_fetch)
    return SupabaseJWTVerifier(jwks_cache=cache, issuer=ISSUER, audience=AUDIENCE)


# ---------------------------------------------------------------------------
# Valid token
# ---------------------------------------------------------------------------


def test_valid_token_resolves_sub_as_uuid(keypair, verifier) -> None:
    private_key, _ = keypair
    sub = str(uuid.uuid4())
    token = _make_token(private_key, overrides={"sub": sub})

    assert verifier.verify(token) == uuid.UUID(sub)


# ---------------------------------------------------------------------------
# Claim validation failures
# ---------------------------------------------------------------------------


def test_expired_token_rejected(keypair, verifier) -> None:
    private_key, _ = keypair
    now = datetime.datetime.now(datetime.timezone.utc)
    token = _make_token(
        private_key,
        overrides={
            "iat": now - datetime.timedelta(hours=2),
            "exp": now - datetime.timedelta(hours=1),
        },
    )

    with pytest.raises(AuthenticationError):
        verifier.verify(token)


def test_invalid_signature_rejected(keypair, verifier) -> None:
    other_private_key, _ = _generate_keypair()
    token = _make_token(other_private_key)  # signed with a key NOT in the JWKS

    with pytest.raises(AuthenticationError):
        verifier.verify(token)


def test_forged_algorithm_rejected(keypair, verifier) -> None:
    private_key, _ = keypair
    token = _make_token(private_key)
    forged = _tamper_header(token, alg="HS256")

    with pytest.raises(AuthenticationError):
        verifier.verify(forged)


def test_malformed_token_rejected(verifier) -> None:
    with pytest.raises(AuthenticationError):
        verifier.verify("not-a-jwt-at-all")


@pytest.mark.parametrize("missing_claim", ["sub", "exp", "iat", "aud", "iss"])
def test_missing_required_claim_rejected(keypair, verifier, missing_claim: str) -> None:
    private_key, _ = keypair
    token = _make_token(private_key, omit=[missing_claim])

    with pytest.raises(AuthenticationError):
        verifier.verify(token)


def test_invalid_uuid_sub_rejected(keypair, verifier) -> None:
    private_key, _ = keypair
    token = _make_token(private_key, overrides={"sub": "not-a-uuid"})

    with pytest.raises(AuthenticationError):
        verifier.verify(token)


def test_wrong_audience_rejected(keypair, verifier) -> None:
    private_key, _ = keypair
    token = _make_token(private_key, overrides={"aud": "anon"})

    with pytest.raises(AuthenticationError):
        verifier.verify(token)


def test_wrong_issuer_rejected(keypair, verifier) -> None:
    private_key, _ = keypair
    token = _make_token(private_key, overrides={"iss": "https://attacker.example/auth/v1"})

    with pytest.raises(AuthenticationError):
        verifier.verify(token)


# ---------------------------------------------------------------------------
# JWKS caching, unknown-kid refresh, rotation, and refresh throttling
# ---------------------------------------------------------------------------


def test_unknown_kid_triggers_a_refresh(keypair) -> None:
    private_key, public_key = keypair
    jwk = _public_key_to_jwk(public_key, "kid-v2")
    fetch_calls = []

    def fake_fetch(_uri: str) -> dict:
        fetch_calls.append(1)
        return {"keys": [jwk]}

    cache = JWKSCache("https://unused.example/jwks.json", fetch=fake_fetch)
    verifier = SupabaseJWTVerifier(jwks_cache=cache, issuer=ISSUER, audience=AUDIENCE)
    token = _make_token(private_key, kid="kid-v2")

    assert isinstance(verifier.verify(token), uuid.UUID)
    assert len(fetch_calls) == 1


def test_rotation_from_one_key_to_another(keypair) -> None:
    old_private, old_public = keypair
    new_private, new_public = _generate_keypair()
    documents = [
        {"keys": [_public_key_to_jwk(old_public, "kid-old")]},
        {
            "keys": [
                _public_key_to_jwk(old_public, "kid-old"),
                _public_key_to_jwk(new_public, "kid-new"),
            ]
        },
    ]
    call_count = {"n": 0}

    def fake_fetch(_uri: str) -> dict:
        document = documents[min(call_count["n"], len(documents) - 1)]
        call_count["n"] += 1
        return document

    clock_state = {"now": datetime.datetime.now(datetime.timezone.utc)}
    cache = JWKSCache(
        "https://unused.example/jwks.json",
        fetch=fake_fetch,
        min_refresh_interval=datetime.timedelta(minutes=5),
        clock=lambda: clock_state["now"],
    )
    verifier = SupabaseJWTVerifier(jwks_cache=cache, issuer=ISSUER, audience=AUDIENCE)

    old_token = _make_token(old_private, kid="kid-old")
    assert isinstance(verifier.verify(old_token), uuid.UUID)

    clock_state["now"] += datetime.timedelta(minutes=6)  # past the throttle window
    new_token = _make_token(new_private, kid="kid-new")
    assert isinstance(verifier.verify(new_token), uuid.UUID)
    assert call_count["n"] == 2


def test_repeated_bogus_kid_does_not_refetch_within_throttle_window(keypair) -> None:
    private_key, public_key = keypair
    jwk = _public_key_to_jwk(public_key, "real-kid")
    call_count = {"n": 0}

    def fake_fetch(_uri: str) -> dict:
        call_count["n"] += 1
        return {"keys": [jwk]}

    clock_state = {"now": datetime.datetime.now(datetime.timezone.utc)}
    cache = JWKSCache(
        "https://unused.example/jwks.json",
        fetch=fake_fetch,
        min_refresh_interval=datetime.timedelta(minutes=5),
        clock=lambda: clock_state["now"],
    )
    verifier = SupabaseJWTVerifier(jwks_cache=cache, issuer=ISSUER, audience=AUDIENCE)

    for _ in range(5):
        bogus_token = _make_token(private_key, kid="bogus-kid")
        with pytest.raises(AuthenticationError):
            verifier.verify(bogus_token)

    assert call_count["n"] == 1  # only the first bogus kid triggered a real fetch


# ---------------------------------------------------------------------------
# Issuer/JWKS-URI derivation from settings (pins the verified relationship
# to SUPABASE_URL -- see supabase_jwt.py's module docstring)
# ---------------------------------------------------------------------------


def test_build_verifier_derives_issuer_and_jwks_uri_from_supabase_url() -> None:
    settings = Settings(supabase_url="https://example-project.supabase.co")
    verifier = build_verifier_from_settings(settings)

    assert verifier.issuer == "https://example-project.supabase.co/auth/v1"
    assert (
        verifier.jwks_cache.jwks_uri
        == "https://example-project.supabase.co/auth/v1/.well-known/jwks.json"
    )
    assert verifier.audience == "authenticated"


def test_build_verifier_raises_when_supabase_url_missing() -> None:
    settings = Settings(supabase_url=None)

    with pytest.raises(RuntimeError):
        build_verifier_from_settings(settings)
