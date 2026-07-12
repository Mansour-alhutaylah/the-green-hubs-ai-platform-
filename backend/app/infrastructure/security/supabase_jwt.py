"""Framework-independent verification of Supabase-issued access tokens.

This project's Supabase instance uses asymmetric signing keys (confirmed
during Sprint 3.3 planning by querying the live JWKS endpoint directly: it
returned a real ``ES256`` public key, not an empty key set -- an empty set
is what a legacy HS256-only project's JWKS endpoint would return). Verification
here is always against the project's JWKS public keys via ``kid``-based
selection -- never a shared secret, and no private key material is ever
required or stored.

The expected issuer (``f"{supabase_url}/auth/v1"``) and JWKS URI
(``f"{supabase_url}/auth/v1/.well-known/jwks.json"``) are derived from
``settings.supabase_url`` rather than hardcoded. This derivation was
verified against the live OIDC discovery document
(``/auth/v1/.well-known/openid-configuration``) during planning, not
assumed -- ``tests/infrastructure/security/test_supabase_jwt.py`` pins the
derivation itself so a future change can't silently drift from what was
verified.

The allowed algorithm (``ES256``) is a hardcoded constant, not a
``Settings`` field: the JWT algorithm allow-list is a security control
that must never be weakenable via environment misconfiguration. PyJWT
itself refuses to verify a token whose header declares any algorithm not
in the explicit list passed to ``jwt.decode`` -- the token's own ``alg``
is never trusted to select the verification method.

This module raises ``AuthenticationError`` (an ``AppError`` subclass)
directly on any verification failure, exactly as
``SQLAlchemyOrganizationRepository`` already raises ``NotFoundError``
directly from the infrastructure layer -- the "framework-agnostic" rule in
this codebase applies strictly to ``domain/``, not ``infrastructure/``.
Every failure path collapses to the same generic message: this module
never reveals *which* validation step failed (expired vs. bad signature vs.
wrong audience, etc.) to a caller.
"""

import json
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import UUID

import jwt

from app.core.config import Settings
from app.core.exceptions import AuthenticationError

_ALLOWED_ALGORITHMS = ["ES256"]
_REQUIRED_CLAIMS = ["exp", "iat", "sub", "aud", "iss"]
_JWKS_FETCH_TIMEOUT_SECONDS = 5

_GENERIC_ERROR = "Invalid authentication credentials"


def _fetch_jwks(jwks_uri: str) -> dict[str, Any]:
    with urllib.request.urlopen(jwks_uri, timeout=_JWKS_FETCH_TIMEOUT_SECONDS) as response:
        return json.loads(response.read())


class JWKSCache:
    """Caches a JWKS document keyed by ``kid``.

    Refreshes on an unknown ``kid`` (required for legitimate key rotation),
    but throttles forced refreshes to at most one per
    ``min_refresh_interval`` -- without this, a burst of tokens carrying
    forged/bogus ``kid`` values could force unbounded requests against the
    JWKS endpoint.
    """

    def __init__(
        self,
        jwks_uri: str,
        *,
        fetch: Callable[[str], dict[str, Any]] = _fetch_jwks,
        min_refresh_interval: timedelta = timedelta(minutes=5),
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._jwks_uri = jwks_uri
        self._fetch = fetch
        self._min_refresh_interval = min_refresh_interval
        self._clock = clock
        self._keys_by_kid: dict[str, dict[str, Any]] = {}
        self._last_refresh: datetime | None = None

    @property
    def jwks_uri(self) -> str:
        return self._jwks_uri

    def get_key(self, kid: str) -> dict[str, Any]:
        if kid not in self._keys_by_kid:
            self._maybe_refresh()
        try:
            return self._keys_by_kid[kid]
        except KeyError as exc:
            raise AuthenticationError(_GENERIC_ERROR) from exc

    def _maybe_refresh(self) -> None:
        now = self._clock()
        if (
            self._last_refresh is not None
            and now - self._last_refresh < self._min_refresh_interval
        ):
            return
        self._last_refresh = now
        try:
            document = self._fetch(self._jwks_uri)
            self._keys_by_kid = {key["kid"]: key for key in document.get("keys", [])}
        except AuthenticationError:
            raise
        except Exception as exc:
            raise AuthenticationError(_GENERIC_ERROR) from exc


@dataclass
class SupabaseJWTVerifier:
    jwks_cache: JWKSCache
    issuer: str
    audience: str
    algorithms: list[str] = field(default_factory=lambda: list(_ALLOWED_ALGORITHMS))

    def verify(self, token: str) -> UUID:
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if not kid:
                raise AuthenticationError(_GENERIC_ERROR)

            jwk = self.jwks_cache.get_key(kid)
            signing_key = jwt.PyJWK.from_dict(jwk).key

            payload = jwt.decode(
                token,
                key=signing_key,
                algorithms=self.algorithms,
                audience=self.audience,
                issuer=self.issuer,
                options={"require": _REQUIRED_CLAIMS},
            )

            sub = payload["sub"]
            return UUID(str(sub))
        except AuthenticationError:
            raise
        except (jwt.InvalidTokenError, ValueError, TypeError, KeyError) as exc:
            raise AuthenticationError(_GENERIC_ERROR) from exc


def build_verifier_from_settings(settings: Settings) -> SupabaseJWTVerifier:
    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL must be configured to verify Supabase-issued tokens")
    base = settings.supabase_url.rstrip("/")
    return SupabaseJWTVerifier(
        jwks_cache=JWKSCache(f"{base}/auth/v1/.well-known/jwks.json"),
        issuer=f"{base}/auth/v1",
        audience=settings.supabase_jwt_audience,
    )
