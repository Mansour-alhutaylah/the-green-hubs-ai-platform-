"""The outbound orchestration client: destination safety, retries, mapping.

Drives the real ``N8NAIOSClient`` through an ``httpx.MockTransport``, so
the assertions are about the client's own behaviour rather than a stub's.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest

from app.core.config import Settings
from app.domain.aios.client import (
    AIOSDispatch,
    AIOSTimeoutError,
    AIOSUnavailableError,
    AIOSUnexpectedResponseError,
)
from app.domain.aios.workflows import (
    NORA_HEALTH_CHECK,
    TEST_WEBHOOK_ENVIRONMENTS,
    resolve_workflow,
)
from app.infrastructure.aios.internal_signature import (
    HEADER_KEY_ID,
    HEADER_REQUEST_ID,
    HEADER_SIGNATURE,
    HEADER_TIMESTAMP,
    SigningKeyRing,
    verify_signed_request,
)
from app.infrastructure.aios.n8n_client import (
    N8NAIOSClient,
    validate_orchestrator_base_url,
)

#: Read from the shared fixture rather than restated here, so the test
#: literal exists in exactly one file. These tests generate and verify
#: their own signatures, so any value would work -- keeping it single-
#: sourced is about never having a second secret-shaped string in the
#: repository to find, grep for, or accidentally promote.
_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "fixtures" / "aios_signature_vectors.json"
)
SECRET: str = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))["secret_utf8"]
KEY_ID = "gh-aios-f2n-dev-001"
FIXED_NOW = datetime(2026, 8, 12, 14, 47, 5, tzinfo=timezone.utc)
REQUEST_ID = UUID("550e8400-e29b-41d4-a716-446655440000")
CORRELATION_ID = UUID("7c9e6679-7425-40de-944b-e07fc1f90ae7")

PRODUCTION_BASE_URL = "https://thegreenhubs.app.n8n.cloud"


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "production",
        "aios_enabled": True,
        "aios_n8n_base_url": PRODUCTION_BASE_URL,
        "aios_connect_timeout_seconds": 5.0,
        "aios_request_timeout_seconds": 10.0,
    }
    values.update(overrides)
    return Settings(**values)


def _key_ring() -> SigningKeyRing:
    return SigningKeyRing(keys={KEY_ID: SECRET}, active_key_id=KEY_ID)


def _dispatch(body: bytes = b'{"contract_version":"1.0"}') -> AIOSDispatch:
    workflow = resolve_workflow(NORA_HEALTH_CHECK)
    assert workflow is not None
    return AIOSDispatch(
        workflow=workflow,
        envelope_bytes=body,
        request_id=REQUEST_ID,
        correlation_id=CORRELATION_ID,
    )


def _client(handler: Any, **settings_overrides: Any) -> N8NAIOSClient:
    return N8NAIOSClient(
        _settings(**settings_overrides),
        _key_ring(),
        clock=lambda: FIXED_NOW,
        transport=httpx.MockTransport(handler),
    )


def _ok_body(dispatch: AIOSDispatch) -> bytes:
    return json.dumps(
        {
            "contract_version": "1.0",
            "request_id": str(dispatch.request_id),
            "workflow": dispatch.workflow.identifier,
            "status": "completed",
            "output": {},
            "metadata": {},
        }
    ).encode()


# ---------------------------------------------------------------------------
# Base URL validation -- the destination comes from configuration only
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        PRODUCTION_BASE_URL,
        "https://thegreenhubs.app.n8n.cloud/",
        "https://staging-thegreenhubs.app.n8n.cloud",
        "https://n8n.example.com:8443",
        "https://n8n.example.com/base-path",
    ],
)
def test_approved_style_urls_are_accepted(url: str) -> None:
    """The rule must not be so tight that a legitimate staging or
    self-hosted production host cannot be configured -- a rule people
    have to work around is worse than no rule."""

    assert validate_orchestrator_base_url(url, environment="production")


def test_a_trailing_slash_is_normalised() -> None:
    """The registry path is appended, so a trailing slash would produce a
    doubled separator."""

    assert (
        validate_orchestrator_base_url(f"{PRODUCTION_BASE_URL}/", environment="production")
        == PRODUCTION_BASE_URL
    )


@pytest.mark.parametrize(
    "url,reason",
    [
        (None, "missing"),
        ("", "empty"),
        ("   ", "whitespace only"),
        ("http://thegreenhubs.app.n8n.cloud", "plaintext http"),
        ("ftp://thegreenhubs.app.n8n.cloud", "wrong scheme"),
        ("//thegreenhubs.app.n8n.cloud", "scheme-relative"),
        ("https://", "no host"),
        ("https://user:pass@thegreenhubs.app.n8n.cloud", "embedded credentials"),
        ("https://user@thegreenhubs.app.n8n.cloud", "embedded username"),
        ("https://thegreenhubs.app.n8n.cloud?token=x", "query string"),
        ("https://thegreenhubs.app.n8n.cloud#frag", "fragment"),
    ],
)
def test_unsafe_urls_are_refused(url: str | None, reason: str) -> None:
    with pytest.raises(RuntimeError):
        validate_orchestrator_base_url(url, environment="production")


@pytest.mark.parametrize(
    "url",
    [
        "https://localhost",
        "https://localhost:5678",
        "https://127.0.0.1",
        "https://10.0.0.5",
        "https://192.168.1.10",
        "https://172.16.0.1",
        "https://n8n.localhost",
    ],
)
def test_loopback_and_private_targets_are_refused_in_production(url: str) -> None:
    """Signed traffic must not be aimable at an internal service."""

    with pytest.raises(RuntimeError):
        validate_orchestrator_base_url(url, environment="production")


@pytest.mark.parametrize("environment", ["test", "development", "local", "TESTING"])
def test_loopback_is_allowed_in_a_non_production_environment(environment: str) -> None:
    """A developer running n8n locally is a legitimate configuration."""

    assert validate_orchestrator_base_url("https://localhost:5678", environment=environment)


def test_the_client_refuses_to_construct_without_a_base_url() -> None:
    with pytest.raises(RuntimeError):
        N8NAIOSClient(_settings(aios_n8n_base_url=None), _key_ring())


@pytest.mark.parametrize(
    "overrides",
    [
        {"aios_request_timeout_seconds": 0},
        {"aios_request_timeout_seconds": -1},
        {"aios_connect_timeout_seconds": 0},
    ],
)
def test_the_client_refuses_a_nonsensical_timeout(overrides: dict[str, Any]) -> None:
    with pytest.raises(RuntimeError):
        N8NAIOSClient(_settings(**overrides), _key_ring())


# ---------------------------------------------------------------------------
# The caller cannot influence the destination
# ---------------------------------------------------------------------------


async def test_the_destination_is_built_only_from_configuration_and_registry() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=_ok_body(_dispatch()))

    await _client(handler).invoke(_dispatch())

    url = seen[0].url
    assert str(url) == (
        f"{PRODUCTION_BASE_URL}/webhook/gh-aios/v1/nora/health-check"
    )
    assert url.scheme == "https"
    assert url.host == "thegreenhubs.app.n8n.cloud"
    assert url.query == b""


async def test_staging_test_mode_selects_only_the_reviewed_test_path() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=_ok_body(_dispatch()))

    await _client(
        handler,
        environment="staging",
        aios_n8n_webhook_mode="test",
    ).invoke(_dispatch())

    assert str(seen[0].url) == (
        f"{PRODUCTION_BASE_URL}/webhook-test/gh-aios/v1/nora/health-check"
    )


@pytest.mark.parametrize("environment", sorted(TEST_WEBHOOK_ENVIRONMENTS))
def test_the_client_accepts_test_mode_in_every_reviewed_environment(
    environment: str,
) -> None:
    _client(
        lambda request: httpx.Response(200, content=b"{}"),
        environment=environment,
        aios_n8n_webhook_mode="test",
    )


@pytest.mark.parametrize(
    "environment", ["production", "prod", "", "   ", "preview", "stage", "unknown"]
)
def test_the_client_refuses_test_mode_in_any_other_environment(
    environment: str,
) -> None:
    with pytest.raises(RuntimeError):
        _client(
            lambda request: httpx.Response(200, content=b"{}"),
            environment=environment,
            aios_n8n_webhook_mode="test",
        )


async def test_caller_data_cannot_select_a_webhook_mode_or_path() -> None:
    body = json.dumps(
        {
            "input": {},
            "webhook_mode": "test",
            "webhook_path": "/webhook-test/attacker-controlled",
        },
        separators=(",", ":"),
    ).encode()
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=_ok_body(_dispatch(body)))

    await _client(handler).invoke(_dispatch(body))

    assert seen[0].url.path == "/webhook/gh-aios/v1/nora/health-check"
    assert seen[0].content == body


async def test_only_the_destination_path_changes_between_webhook_modes() -> None:
    body = b'{"contract_version":"1.0","input":{}}'
    production_requests: list[httpx.Request] = []
    test_requests: list[httpx.Request] = []

    def production_handler(request: httpx.Request) -> httpx.Response:
        production_requests.append(request)
        return httpx.Response(200, content=_ok_body(_dispatch(body)))

    def test_handler(request: httpx.Request) -> httpx.Response:
        test_requests.append(request)
        return httpx.Response(200, content=_ok_body(_dispatch(body)))

    await _client(production_handler).invoke(_dispatch(body))
    await _client(
        test_handler,
        environment="staging",
        aios_n8n_webhook_mode="test",
    ).invoke(_dispatch(body))

    production_request = production_requests[0]
    test_request = test_requests[0]
    assert production_request.url.host == test_request.url.host
    assert production_request.url.path == "/webhook/gh-aios/v1/nora/health-check"
    assert test_request.url.path == "/webhook-test/gh-aios/v1/nora/health-check"
    assert production_request.content == test_request.content == body
    for header in (HEADER_KEY_ID, HEADER_TIMESTAMP, HEADER_REQUEST_ID, HEADER_SIGNATURE):
        assert production_request.headers[header] == test_request.headers[header]


async def test_the_transmitted_bytes_are_exactly_the_signed_bytes() -> None:
    """`content=` not `json=`. A re-serialised body would be signed as one
    byte string and sent as another."""

    body = '{"note":"المركز الأخضر — GH","input":{}}'.encode("utf-8")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=_ok_body(_dispatch(body)))

    await _client(handler).invoke(_dispatch(body))

    assert seen[0].content == body


async def test_the_transmitted_request_carries_a_signature_that_verifies() -> None:
    """End-to-end within the process: what the client sends is what the
    verifier accepts."""

    body = b'{"contract_version":"1.0","input":{}}'
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=_ok_body(_dispatch(body)))

    await _client(handler).invoke(_dispatch(body))

    sent = seen[0]
    assert sent.headers["Content-Type"] == "application/json"
    verified = verify_signed_request(
        key_ring=_key_ring(),
        key_id=sent.headers[HEADER_KEY_ID],
        timestamp=sent.headers[HEADER_TIMESTAMP],
        request_id=sent.headers[HEADER_REQUEST_ID],
        workflow=NORA_HEALTH_CHECK,
        signature=sent.headers[HEADER_SIGNATURE],
        body=sent.content,
        now=FIXED_NOW,
    )
    assert verified == REQUEST_ID


# ---------------------------------------------------------------------------
# Redirects are never followed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status_code", [301, 302, 303, 307, 308])
async def test_a_redirect_is_refused_and_never_followed(status_code: int) -> None:
    """httpx forwards headers on a same-scheme redirect. A followed
    redirect would hand a valid signature to a host that did not
    originate the request."""

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status_code, headers={"Location": "https://evil.example/steal"})

    with pytest.raises(AIOSUnexpectedResponseError):
        await _client(handler).invoke(_dispatch())

    assert len(seen) == 1, "the redirect was followed"
    assert seen[0].url.host == "thegreenhubs.app.n8n.cloud"


async def test_the_client_is_configured_with_redirects_disabled() -> None:
    """Asserted on the client object itself, so the property survives a
    refactor of the request path."""

    client = _client(lambda request: httpx.Response(200, content=b"{}"))
    assert client._client().follow_redirects is False  # noqa: SLF001


# ---------------------------------------------------------------------------
# Retry policy
# ---------------------------------------------------------------------------


async def test_a_5xx_is_retried_exactly_once_more_then_reported_unavailable() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(503)

    with pytest.raises(AIOSUnavailableError):
        await _client(handler).invoke(_dispatch())

    assert len(attempts) == 2, "bounded at two attempts total"


async def test_a_transient_5xx_that_recovers_succeeds_on_the_second_attempt() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(502)
        return httpx.Response(200, content=_ok_body(_dispatch()))

    result = await _client(handler).invoke(_dispatch())

    assert len(attempts) == 2
    assert result["status"] == "completed"


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 409, 422, 429])
async def test_a_4xx_is_never_retried(status_code: int) -> None:
    """Our request was refused. Repeating an identical refused request is
    pure load -- and a refused *signature* cannot become valid."""

    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(status_code)

    with pytest.raises(AIOSUnexpectedResponseError):
        await _client(handler).invoke(_dispatch())

    assert len(attempts) == 1


async def test_a_timeout_is_bounded_and_reported_as_a_timeout() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(AIOSTimeoutError):
        await _client(handler).invoke(_dispatch())

    assert len(attempts) == 2


async def test_a_transport_error_is_bounded_and_reported_as_unavailable() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(AIOSUnavailableError):
        await _client(handler).invoke(_dispatch())

    assert len(attempts) == 2


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "content", [b"not json", b"", b"[]", b'"a string"', b"12", b"null"]
)
async def test_a_non_object_response_is_refused(content: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content)

    with pytest.raises(AIOSUnexpectedResponseError):
        await _client(handler).invoke(_dispatch())


async def test_a_valid_object_response_is_returned_unchanged() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_ok_body(_dispatch()))

    result = await _client(handler).invoke(_dispatch())

    assert result["workflow"] == NORA_HEALTH_CHECK
    assert result["request_id"] == str(REQUEST_ID)
