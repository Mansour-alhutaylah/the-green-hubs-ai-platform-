"""Dispatches signed AIOS envelopes to n8n Cloud over narrow ``httpx``.

Not an SDK: the same rationale as ``OpenAILLMGateway`` and
``SupabaseDocumentStorage``, which both make narrow ``httpx`` calls
rather than pulling a vendor client in for two operations. No new
dependency is introduced by the AIOS layer.

Configuration is validated at construction (fail fast, matching
``OpenAILLMGateway`` and ``OpenAIEmbeddingProvider``): a missing base
URL, a non-TLS base URL, an unusable key ring or a non-positive timeout
raises immediately rather than on the first request.

**Retry policy**, mirroring the existing gateway so the codebase has one
philosophy rather than two: at most two attempts, and only for transport
failures and 5xx. A 4xx is never retried -- the orchestrator rejecting
our request means our signature, our contract or our configuration is
wrong, and repeating it cannot help. Neither is a timeout retried after
the budget is spent.
"""

import json
import logging
from datetime import datetime, timezone
from ipaddress import ip_address
from typing import Any, Callable, Final, Mapping
from urllib.parse import urlsplit

import httpx

from app.core.config import Settings
from app.core.request_context import CORRELATION_HEADER_NAME
from app.domain.aios.client import (
    AIOSClient,
    AIOSDispatch,
    AIOSTimeoutError,
    AIOSUnavailableError,
    AIOSUnexpectedResponseError,
)
from app.infrastructure.aios.internal_signature import (
    SigningKeyRing,
    build_signature_headers,
)

logger = logging.getLogger(__name__)

_MAX_TRANSIENT_ATTEMPTS: Final = 2
_TLS_SCHEME: Final = "https"

#: Environments in which a loopback or private orchestrator address is a
#: legitimate configuration (a developer running n8n locally). Anywhere
#: else it is either a mistake or an attempt to redirect signed traffic
#: at an internal service.
_NON_PRODUCTION_ENVIRONMENTS: Final[frozenset[str]] = frozenset(
    {"test", "testing", "development", "local"}
)

_PRIVATE_HOST_NAMES: Final[frozenset[str]] = frozenset(
    {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
)


def validate_orchestrator_base_url(raw: str | None, *, environment: str) -> str:
    """Validate the configured orchestrator base URL, or raise.

    The destination of a signed request must come from trusted
    configuration and nothing else. No API caller can influence it -- the
    scheme, host, port and path are all fixed here and in the workflow
    registry -- so this function's job is to make sure the *operator*
    cannot configure something unsafe by accident either.

    Rejected, each for its own reason:

    * a missing or empty URL -- fail closed rather than guess;
    * a non-``https`` scheme -- a plaintext base URL would put the signed
      envelope, including resolved actor context, on the wire in clear;
    * embedded credentials (``https://user:pass@host``) -- a secret in a
      URL is a secret in every log that records the URL;
    * a query string or fragment -- the workflow's path is appended to
      this value, so either one silently produces a different URL than
      the one that was reviewed;
    * a loopback or private host outside a non-production environment.

    Deliberately *not* rejected: a non-default port, and any public
    hostname. Staging and production are ordinary n8n Cloud subdomains,
    and a rule tight enough to exclude a future staging host would be a
    rule someone works around.

    Returns the URL with any trailing slash removed, so appending a
    registry path cannot produce a doubled separator.
    """

    if not raw or not raw.strip():
        raise RuntimeError("AIOS_N8N_BASE_URL is required to construct N8NAIOSClient")

    parsed = urlsplit(raw.strip())

    if parsed.scheme != _TLS_SCHEME:
        raise RuntimeError("AIOS_N8N_BASE_URL must use https://")
    if not parsed.hostname:
        raise RuntimeError("AIOS_N8N_BASE_URL must include a host")
    if parsed.username or parsed.password:
        raise RuntimeError("AIOS_N8N_BASE_URL must not embed credentials")
    if parsed.query:
        raise RuntimeError("AIOS_N8N_BASE_URL must not include a query string")
    if parsed.fragment:
        raise RuntimeError("AIOS_N8N_BASE_URL must not include a fragment")

    host = parsed.hostname.lower()
    if environment.strip().lower() not in _NON_PRODUCTION_ENVIRONMENTS:
        if host in _PRIVATE_HOST_NAMES or host.endswith(".localhost"):
            raise RuntimeError(
                "AIOS_N8N_BASE_URL must not target a loopback host outside a "
                "non-production environment"
            )
        try:
            if ip_address(host).is_private:
                raise RuntimeError(
                    "AIOS_N8N_BASE_URL must not target a private address outside a "
                    "non-production environment"
                )
        except ValueError:
            # Not a literal IP address; an ordinary hostname is fine.
            pass

    return raw.strip().rstrip("/")


class N8NAIOSClient(AIOSClient):
    """The n8n Cloud implementation of :class:`AIOSClient`."""

    def __init__(
        self,
        settings: Settings,
        key_ring: SigningKeyRing,
        *,
        clock: Callable[[], datetime] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        base_url = validate_orchestrator_base_url(
            settings.aios_n8n_base_url, environment=settings.environment
        )
        if settings.aios_request_timeout_seconds <= 0:
            raise RuntimeError("aios_request_timeout_seconds must be positive")
        if settings.aios_connect_timeout_seconds <= 0:
            raise RuntimeError("aios_connect_timeout_seconds must be positive")

        self._base_url = base_url
        self._key_ring = key_ring
        self._timeout = httpx.Timeout(
            settings.aios_request_timeout_seconds,
            connect=settings.aios_connect_timeout_seconds,
        )
        self._transport = transport
        # Injected only by tests; production always reads the real clock.
        self._clock: Callable[[], datetime] = clock or (
            lambda: datetime.now(timezone.utc)
        )

    def _client(self) -> httpx.AsyncClient:
        # `follow_redirects=False` is httpx's default, but it is stated
        # explicitly because it is a security property, not a
        # preference: the request carries signing headers, and httpx
        # forwards headers on a same-scheme redirect. A compromised or
        # misconfigured orchestrator answering 302 to another host would
        # otherwise receive a valid signature for a body it did not
        # originate. A redirect is treated as an unexpected response.
        return httpx.AsyncClient(
            timeout=self._timeout, transport=self._transport, follow_redirects=False
        )

    async def invoke(self, dispatch: AIOSDispatch) -> Mapping[str, Any]:
        url = f"{self._base_url}{dispatch.workflow.webhook_path}"
        headers = build_signature_headers(
            key_ring=self._key_ring,
            workflow=dispatch.workflow.identifier,
            request_id=dispatch.request_id,
            body=dispatch.envelope_bytes,
            now=self._clock(),
        )
        headers["Content-Type"] = "application/json"
        headers[CORRELATION_HEADER_NAME] = str(dispatch.correlation_id)

        last_error: Exception | None = None
        for _attempt in range(_MAX_TRANSIENT_ATTEMPTS):
            try:
                async with self._client() as client:
                    # `content=` transmits exactly the bytes that were
                    # signed. `json=` would re-serialize the envelope, so
                    # the digest inside the signature would describe a
                    # different byte string than the one sent -- and every
                    # request would fail verification for a reason that
                    # looks like a key problem.
                    response = await client.post(
                        url, content=dispatch.envelope_bytes, headers=headers
                    )
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("AIOS dispatch timed out, will retry within budget")
                continue
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning("AIOS dispatch transport failure, will retry: %r", exc)
                continue

            if 300 <= response.status_code < 400:
                # Redirects are not followed (see `_client`). A redirect
                # is therefore an answer we cannot trust rather than a
                # hop to take, and it is never retried: repeating it
                # would just produce the same redirect.
                logger.warning(
                    "AIOS orchestrator answered with a redirect status %s; refusing",
                    response.status_code,
                )
                raise AIOSUnexpectedResponseError(
                    "orchestrator answered with a redirect, which is not followed"
                )

            if response.status_code >= 500:
                last_error = AIOSUnavailableError(
                    f"orchestrator returned status {response.status_code}"
                )
                logger.warning(
                    "AIOS orchestrator returned status %s, will retry",
                    response.status_code,
                )
                continue

            if response.status_code >= 400:
                # Our request was refused. Retrying an identical refused
                # request is pure load.
                logger.warning(
                    "AIOS orchestrator refused the request with status %s",
                    response.status_code,
                )
                raise AIOSUnexpectedResponseError(
                    f"orchestrator refused the request with status {response.status_code}"
                )

            return self._parse(response)

        if isinstance(last_error, httpx.TimeoutException):
            raise AIOSTimeoutError("orchestrator did not respond in time") from last_error
        raise AIOSUnavailableError("orchestrator unavailable after retries") from last_error

    def _parse(self, response: httpx.Response) -> Mapping[str, Any]:
        try:
            body = json.loads(response.content)
        except (ValueError, TypeError) as exc:
            raise AIOSUnexpectedResponseError(
                "orchestrator returned a body that is not valid JSON"
            ) from exc
        if not isinstance(body, dict):
            raise AIOSUnexpectedResponseError(
                "orchestrator returned a body that is not a JSON object"
            )
        return body
