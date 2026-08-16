"""The AIOS API boundary: authorization, contract, and safe error mapping.

Drives the real routers through ``dependency_overrides`` -- no Supabase,
no database, no orchestrator. The allowed and denied role sets are
derived from ``ROLE_PERMISSIONS`` rather than hardcoded, so these tests
follow the policy instead of quietly defining a second one.
"""

import base64
import inspect
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

import pytest
from httpx import AsyncClient

from app.api.deps import (
    get_aios_verification_rate_limiter,
    get_app_settings,
    get_health_check_service,
    get_request_verification_service,
    get_supabase_jwt_verifier,
    get_user_repository,
)
from app.core.config import Settings
from app.core.request_context import CORRELATION_HEADER_NAME
from app.domain.aios.client import (
    AIOSClient,
    AIOSDispatch,
    AIOSTimeoutError,
    AIOSUnavailableError,
    AIOSUnexpectedResponseError,
)
from app.domain.aios.contracts import (
    CONTRACT_VERSION,
    FORBIDDEN_ACTOR_FIELDS,
    GENERIC_VERIFICATION_FAILURE,
)
from app.domain.aios.workflows import NORA_HEALTH_CHECK
from app.domain.entities.user import User
from app.domain.security import Permission
from app.domain.security.permissions import ROLE_PERMISSIONS
from app.infrastructure.aios.internal_signature import (
    SigningKeyRing,
    build_signature_headers,
)
from app.infrastructure.aios.rate_limit import FixedWindowRateLimiter
from app.main import app
from app.services.aios.health_check import HealthCheckService
from app.services.aios.request_verification import RequestVerificationService

from tests.api.test_auth import FakeUserRepository, FakeVerifier

INVOKE_PATH = f"/api/v1/aios/workflows/{NORA_HEALTH_CHECK}"
VERIFY_PATH = "/api/v1/internal/aios/verify-request"

FIXED_NOW = datetime(2026, 8, 12, 14, 47, 5, tzinfo=timezone.utc)
FIXED_REQUEST_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "aios_signature_vectors.json"
SECRET: str = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["secret_utf8"]
KEY_ID = "gh-aios-f2n-dev-001"

# The policy decides which roles may invoke -- these tests only read it.
ALLOWED_ROLES = tuple(
    sorted(
        role.value
        for role, permissions in ROLE_PERMISSIONS.items()
        if Permission.AIOS_INVOKE in permissions
    )
)
DENIED_ROLES = tuple(
    sorted(
        role.value
        for role, permissions in ROLE_PERMISSIONS.items()
        if Permission.AIOS_INVOKE not in permissions
    )
)
UNRECOGNIZED_ROLES = ("member", "superuser", "", "root", None)


class StubClient(AIOSClient):
    """Records dispatches; returns a scripted response or raises."""

    def __init__(
        self, response: Mapping[str, Any] | None = None, error: Exception | None = None
    ) -> None:
        self.dispatches: list[AIOSDispatch] = []
        self._response = response
        self._error = error

    async def invoke(self, dispatch: AIOSDispatch) -> Mapping[str, Any]:
        self.dispatches.append(dispatch)
        if self._error is not None:
            raise self._error
        return self._response or _orchestrator_response(dispatch)


def _orchestrator_response(dispatch: AIOSDispatch) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "request_id": str(dispatch.request_id),
        "correlation_id": str(dispatch.correlation_id),
        "workflow": dispatch.workflow.identifier,
        "status": "completed",
        "output": {
            "service": "gh-aios",
            "orchestrator": "n8n",
            "role": "NORA",
            "health": "ok",
        },
        "metadata": {
            "execution_id": "42",
            "workflow_version": "1.0.0",
            "started_at": "2026-08-12T14:47:05Z",
            "completed_at": "2026-08-12T14:47:05Z",
        },
    }


@pytest.fixture
def fake_repository() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def fake_verifier() -> FakeVerifier:
    return FakeVerifier()


@pytest.fixture
def stub_client() -> StubClient:
    return StubClient()


@pytest.fixture
def key_ring() -> SigningKeyRing:
    return SigningKeyRing(keys={KEY_ID: SECRET}, active_key_id=KEY_ID)


@pytest.fixture
def rate_limiter() -> FixedWindowRateLimiter:
    return FixedWindowRateLimiter(limit=1000, window_seconds=60)


@pytest.fixture(autouse=True)
def _override_dependencies(
    fake_repository: FakeUserRepository,
    fake_verifier: FakeVerifier,
    stub_client: StubClient,
    key_ring: SigningKeyRing,
    rate_limiter: FixedWindowRateLimiter,
) -> Iterator[None]:
    app.dependency_overrides[get_supabase_jwt_verifier] = lambda: fake_verifier
    app.dependency_overrides[get_user_repository] = lambda: fake_repository
    app.dependency_overrides[get_health_check_service] = lambda: HealthCheckService(
        stub_client, clock=lambda: FIXED_NOW, request_id_factory=lambda: FIXED_REQUEST_ID
    )
    app.dependency_overrides[get_request_verification_service] = (
        lambda: RequestVerificationService(
            key_ring,
            max_clock_skew_seconds=300,
            max_body_bytes=64 * 1024,
            clock=lambda: FIXED_NOW,
        )
    )
    app.dependency_overrides[get_aios_verification_rate_limiter] = lambda: rate_limiter
    yield
    for dependency in (
        get_supabase_jwt_verifier,
        get_user_repository,
        get_health_check_service,
        get_request_verification_service,
        get_aios_verification_rate_limiter,
    ):
        app.dependency_overrides.pop(dependency, None)


def _sign_in(
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    *,
    role: str | None,
    organization_id: uuid.UUID | None = None,
    token: str = "valid-token",
) -> dict[str, str]:
    user_id = uuid.uuid4()
    fake_verifier.register(token, user_id)
    fake_repository.seed(
        User(
            id=user_id,
            organization_id=organization_id if organization_id is not None else uuid.uuid4(),
            full_name="Test User",
            email="test@example.com",
            role=role,
            created_at=FIXED_NOW,
        )
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Authentication and authorization
# ---------------------------------------------------------------------------


async def test_the_policy_actually_splits_the_roles() -> None:
    """Without this, a policy granting nobody (or everybody) would make
    every parametrized test below pass vacuously."""

    assert ALLOWED_ROLES, "no role may invoke -- the policy is broken"
    assert DENIED_ROLES, "every role may invoke -- the viewer bypass is back"
    assert "viewer" in DENIED_ROLES


async def test_the_route_is_gated_to_administrative_roles_only() -> None:
    """The recorded reviewer decision, asserted at the API boundary.

    ``ALLOWED_ROLES``/``DENIED_ROLES`` are derived from
    ``ROLE_PERMISSIONS``, so the parametrized tests below follow the
    policy wherever it goes. This test pins *where it is supposed to be*
    -- otherwise a silent re-widening would simply re-parametrize the
    suite and every case would still pass.
    """

    assert ALLOWED_ROLES == ("admin", "owner")
    assert DENIED_ROLES == ("approver", "editor", "viewer")


async def test_an_unauthenticated_invoke_is_401(client: AsyncClient) -> None:
    response = await client.post(INVOKE_PATH, json={"input": {}})
    assert response.status_code == 401


async def test_an_invalid_token_is_401(client: AsyncClient) -> None:
    response = await client.post(
        INVOKE_PATH, headers={"Authorization": "Bearer nope"}, json={"input": {}}
    )
    assert response.status_code == 401


@pytest.mark.parametrize("role", DENIED_ROLES)
async def test_a_role_without_the_permission_is_403_not_401(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_client: StubClient,
    role: str,
) -> None:
    """The identity is valid; only the permission is missing."""

    headers = _sign_in(fake_verifier, fake_repository, role=role)
    response = await client.post(INVOKE_PATH, headers=headers, json={"input": {}})
    assert response.status_code == 403
    assert stub_client.dispatches == [], "authorization ran before dispatch"


@pytest.mark.parametrize("role", UNRECOGNIZED_ROLES)
async def test_an_unrecognized_role_is_denied(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_client: StubClient,
    role: str | None,
) -> None:
    headers = _sign_in(fake_verifier, fake_repository, role=role)
    response = await client.post(INVOKE_PATH, headers=headers, json={"input": {}})
    assert response.status_code == 403
    assert stub_client.dispatches == []


@pytest.mark.parametrize("role", ALLOWED_ROLES)
async def test_an_authorized_role_can_invoke(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    role: str,
) -> None:
    headers = _sign_in(fake_verifier, fake_repository, role=role)
    response = await client.post(INVOKE_PATH, headers=headers, json={"input": {}})
    assert response.status_code == 200


async def test_a_user_without_an_organization_is_403(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    user_id = uuid.uuid4()
    fake_verifier.register("valid-token", user_id)
    fake_repository.seed(
        User(
            id=user_id,
            organization_id=None,
            full_name="Test User",
            email="test@example.com",
            role="admin",
            created_at=FIXED_NOW,
        )
    )
    response = await client.post(
        INVOKE_PATH, headers={"Authorization": "Bearer valid-token"}, json={"input": {}}
    )
    assert response.status_code == 403


async def test_aios_invoke_does_not_grant_evidence_review() -> None:
    """Holding ``aios.invoke`` confers no authority over evidence."""

    for role, permissions in ROLE_PERMISSIONS.items():
        if Permission.AIOS_INVOKE in permissions:
            # Roles that hold both do so because the *existing* policy
            # already granted evidence review -- never because AIOS did.
            assert Permission.AIOS_INVOKE != Permission.EVIDENCE_REVIEW
    assert Permission.AIOS_INVOKE.value == "aios.invoke"


# ---------------------------------------------------------------------------
# The happy path and identifier preservation
# ---------------------------------------------------------------------------


async def test_a_valid_invoke_returns_the_response_contract(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _sign_in(fake_verifier, fake_repository, role="admin")
    response = await client.post(INVOKE_PATH, headers=headers, json={"input": {}})

    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == "1.0"
    assert body["workflow"] == NORA_HEALTH_CHECK
    assert body["status"] == "completed"
    assert body["output"] == {
        "service": "gh-aios",
        "orchestrator": "n8n",
        "role": "NORA",
        "health": "ok",
    }
    assert body["metadata"]["workflow_version"] == "1.0.0"
    assert body["metadata"]["execution_id"] == "42"


async def test_an_empty_body_is_accepted_as_empty_input(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _sign_in(fake_verifier, fake_repository, role="admin")
    response = await client.post(INVOKE_PATH, headers=headers)
    assert response.status_code == 200


async def test_identifiers_are_preserved_end_to_end(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_client: StubClient,
) -> None:
    headers = _sign_in(fake_verifier, fake_repository, role="admin")
    correlation_id = str(uuid.uuid4())
    headers[CORRELATION_HEADER_NAME] = correlation_id

    response = await client.post(INVOKE_PATH, headers=headers, json={"input": {}})
    body = response.json()

    assert body["correlation_id"] == correlation_id
    assert response.headers[CORRELATION_HEADER_NAME] == correlation_id
    assert body["request_id"] == str(FIXED_REQUEST_ID)

    envelope = json.loads(stub_client.dispatches[0].envelope_bytes)
    assert envelope["correlation_id"] == correlation_id
    assert envelope["request_id"] == str(FIXED_REQUEST_ID)


async def test_the_envelope_carries_the_server_resolved_actor(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_client: StubClient,
) -> None:
    organization_id = uuid.uuid4()
    headers = _sign_in(
        fake_verifier, fake_repository, role="admin", organization_id=organization_id
    )
    await client.post(INVOKE_PATH, headers=headers, json={"input": {}})

    envelope = json.loads(stub_client.dispatches[0].envelope_bytes)
    assert envelope["actor"]["organization_id"] == str(organization_id)


# ---------------------------------------------------------------------------
# Contract validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", sorted(FORBIDDEN_ACTOR_FIELDS))
async def test_a_client_supplied_authority_field_is_rejected_at_the_top_level(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_client: StubClient,
    field: str,
) -> None:
    headers = _sign_in(fake_verifier, fake_repository, role="admin")
    response = await client.post(
        INVOKE_PATH, headers=headers, json={"input": {}, field: str(uuid.uuid4())}
    )
    assert response.status_code == 422
    assert field in response.json()["detail"], "refused by name, never silently stripped"
    assert stub_client.dispatches == []


@pytest.mark.parametrize("field", sorted(FORBIDDEN_ACTOR_FIELDS))
async def test_a_client_supplied_authority_field_is_rejected_when_nested(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_client: StubClient,
    field: str,
) -> None:
    headers = _sign_in(fake_verifier, fake_repository, role="admin")
    response = await client.post(
        INVOKE_PATH, headers=headers, json={"input": {"actor": {field: "x"}}}
    )
    assert response.status_code == 422
    assert stub_client.dispatches == []


@pytest.mark.parametrize(
    "payload",
    [
        {"input": {}, "unexpected": 1},
        {"input": {"unexpected": 1}},
        {"workflow": "hafidh.master_inbox", "input": {}},
        {"webhook_mode": "test", "input": {}},
        {"webhook_path": "/webhook-test/attacker-controlled", "input": {}},
        {"contract_version": "1.0", "input": {}},
        {"request_id": str(uuid.uuid4()), "input": {}},
        {"input": "not-an-object"},
        [],
        "a string",
        7,
    ],
    ids=[
        "extra-top-level",
        "extra-nested",
        "workflow-override",
        "webhook-mode-override",
        "webhook-path-override",
        "contract-version-override",
        "request-id-override",
        "input-not-object",
        "array-body",
        "string-body",
        "number-body",
    ],
)
async def test_an_invalid_contract_is_422(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_client: StubClient,
    payload: object,
) -> None:
    headers = _sign_in(fake_verifier, fake_repository, role="admin")
    response = await client.post(INVOKE_PATH, headers=headers, json=payload)
    assert response.status_code == 422
    assert stub_client.dispatches == []


async def test_malformed_json_is_422(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _sign_in(fake_verifier, fake_repository, role="admin")
    headers["Content-Type"] = "application/json"
    response = await client.post(INVOKE_PATH, headers=headers, content=b"{not json")
    assert response.status_code == 422


async def test_a_payload_over_the_limit_is_413(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_client: StubClient,
) -> None:
    headers = _sign_in(fake_verifier, fake_repository, role="admin")
    headers["Content-Type"] = "application/json"
    oversized = json.dumps({"input": {}, "pad": "x" * (64 * 1024 + 100)}).encode()

    response = await client.post(INVOKE_PATH, headers=headers, content=oversized)
    assert response.status_code == 413
    assert stub_client.dispatches == [], "refused before parsing"


async def test_an_unregistered_workflow_path_is_404(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    """Reserved-but-unapproved names have no route at all."""

    headers = _sign_in(fake_verifier, fake_repository, role="admin")
    response = await client.post(
        "/api/v1/aios/workflows/hafidh.master_inbox", headers=headers, json={"input": {}}
    )
    assert response.status_code == 404


async def test_aios_disabled_still_returns_503_without_constructing_a_client(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_client: StubClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api import deps

    headers = _sign_in(fake_verifier, fake_repository, role="admin")
    enabled_override = app.dependency_overrides.pop(get_health_check_service)
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        aios_enabled=False,
        environment="production",
        aios_n8n_webhook_mode="test",
    )
    monkeypatch.setattr(
        deps,
        "get_aios_client",
        lambda: pytest.fail("a disabled deployment constructed the n8n client"),
    )
    try:
        response = await client.post(INVOKE_PATH, headers=headers, json={"input": {}})
    finally:
        app.dependency_overrides.pop(get_app_settings, None)
        app.dependency_overrides[get_health_check_service] = enabled_override

    assert response.status_code == 503
    assert stub_client.dispatches == []


# ---------------------------------------------------------------------------
# Safe error mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error,expected_status",
    [
        (AIOSTimeoutError("upstream timed out at n8n-host:443"), 504),
        (AIOSUnavailableError("connection refused to n8n-host:443"), 502),
        (AIOSUnexpectedResponseError("orchestrator refused with status 401"), 502),
    ],
    ids=["timeout", "unavailable", "unexpected"],
)
async def test_upstream_failures_map_to_safe_responses(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_client: StubClient,
    error: Exception,
    expected_status: int,
) -> None:
    stub_client._error = error
    headers = _sign_in(fake_verifier, fake_repository, role="admin")

    response = await client.post(INVOKE_PATH, headers=headers, json={"input": {}})

    assert response.status_code == expected_status
    detail = response.json()["detail"]
    for leak in ("n8n", "443", "refused", "connection", "401", "Traceback", "host"):
        assert leak.lower() not in detail.lower(), f"error detail leaks {leak!r}"


async def test_no_response_ever_carries_signing_material(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _sign_in(fake_verifier, fake_repository, role="admin")
    response = await client.post(INVOKE_PATH, headers=headers, json={"input": {}})

    serialized = response.text.lower()
    for leak in (SECRET.lower(), KEY_ID, "sha256=", "hmac", "canonical", "secret"):
        assert leak not in serialized


# ---------------------------------------------------------------------------
# The internal verification endpoint
# ---------------------------------------------------------------------------


def _verification_payload(
    *,
    body: bytes = b"{}",
    workflow: str = NORA_HEALTH_CHECK,
    now: datetime = FIXED_NOW,
    key_ring: SigningKeyRing | None = None,
    **overrides: str,
) -> dict[str, str]:
    ring = key_ring or SigningKeyRing(keys={KEY_ID: SECRET}, active_key_id=KEY_ID)
    signed = build_signature_headers(
        key_ring=ring,
        workflow=workflow,
        request_id=FIXED_REQUEST_ID,
        body=body,
        now=now,
    )
    payload = {
        "workflow": workflow,
        "key_id": signed["X-GH-AIOS-Key-Id"],
        "timestamp": signed["X-GH-AIOS-Timestamp"],
        "request_id": signed["X-GH-Request-Id"],
        "signature": signed["X-GH-AIOS-Signature"],
        "body_base64": base64.b64encode(body).decode("ascii"),
    }
    payload.update(overrides)
    return payload


async def test_a_valid_signature_verifies(client: AsyncClient) -> None:
    response = await client.post(VERIFY_PATH, json=_verification_payload())
    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "request_id": str(FIXED_REQUEST_ID),
        "category": None,
    }


async def test_the_verification_endpoint_needs_no_end_user_token(
    client: AsyncClient,
) -> None:
    """By design: the orchestrator has no end-user token to present. It is
    protected by what it cannot do, not by who calls it."""

    response = await client.post(VERIFY_PATH, json=_verification_payload())
    assert response.status_code == 200


@pytest.mark.parametrize(
    "overrides,description",
    [
        ({"signature": "sha256=" + "0" * 64}, "wrong signature"),
        ({"signature": "sha256=abc"}, "malformed signature length"),
        ({"signature": "not-prefixed"}, "missing prefix"),
        ({"signature": ""}, "empty signature"),
        ({"key_id": "gh-aios-f2n-dev-999"}, "unknown key id"),
        ({"key_id": "NOT VALID"}, "malformed key id"),
        ({"request_id": str(uuid.uuid4())}, "different request id"),
        ({"request_id": "not-a-uuid"}, "malformed request id"),
        ({"timestamp": "2026-08-12T14:52:06Z"}, "timestamp out of window"),
        ({"timestamp": "2026-08-12T14:42:04Z"}, "timestamp too old"),
        ({"timestamp": "2026-08-12T14:47:05.000Z"}, "non-canonical timestamp"),
        ({"body_base64": base64.b64encode(b'{"x":1}').decode()}, "changed body"),
        ({"body_base64": "not base64!!"}, "malformed base64"),
        ({"workflow": "hafidh.master_inbox"}, "unregistered workflow"),
    ],
)
async def test_every_verification_failure_answers_identically(
    client: AsyncClient, overrides: dict[str, str], description: str
) -> None:
    """One generic answer for all of them. Distinguishing "unsupported key
    id" from "bad signature" would turn this into an oracle."""

    response = await client.post(
        VERIFY_PATH, json=_verification_payload(**overrides)
    )
    assert response.status_code == 200, description
    assert response.json() == {
        "valid": False,
        "request_id": None,
        "category": GENERIC_VERIFICATION_FAILURE.value,
    }, description


async def test_a_malformed_verification_payload_is_answered_the_same_way(
    client: AsyncClient,
) -> None:
    for payload in ({}, {"workflow": NORA_HEALTH_CHECK}, {"unexpected": 1}):
        response = await client.post(VERIFY_PATH, json=payload)
        assert response.status_code == 200
        assert response.json()["valid"] is False
        assert response.json()["category"] == GENERIC_VERIFICATION_FAILURE.value


async def test_the_verification_response_never_leaks(client: AsyncClient) -> None:
    for payload in (_verification_payload(), _verification_payload(signature="sha256=" + "0" * 64)):
        response = await client.post(VERIFY_PATH, json=payload)
        serialized = response.text.lower()
        for leak in (SECRET.lower(), "canonical", "digest", "expected", "hmac", "traceback"):
            assert leak not in serialized


async def test_rotation_overlap_verifies_under_both_keys(client: AsyncClient) -> None:
    """Proved through the real endpoint, not only in the unit tests."""

    old_key, new_key = KEY_ID, "gh-aios-f2n-dev-002"
    ring = SigningKeyRing(keys={old_key: SECRET, new_key: SECRET}, active_key_id=new_key)
    app.dependency_overrides[get_request_verification_service] = (
        lambda: RequestVerificationService(
            ring, max_clock_skew_seconds=300, max_body_bytes=64 * 1024, clock=lambda: FIXED_NOW
        )
    )
    try:
        for active in (old_key, new_key):
            payload = _verification_payload(
                key_ring=SigningKeyRing(keys={active: SECRET}, active_key_id=active)
            )
            response = await client.post(VERIFY_PATH, json=payload)
            assert response.json()["valid"] is True, active
    finally:
        app.dependency_overrides.pop(get_request_verification_service, None)


async def test_a_retired_key_stops_verifying_through_the_endpoint(
    client: AsyncClient,
) -> None:
    retired = "gh-aios-f2n-dev-000"
    payload = _verification_payload(
        key_ring=SigningKeyRing(keys={retired: SECRET}, active_key_id=retired)
    )
    response = await client.post(VERIFY_PATH, json=payload)
    assert response.json()["valid"] is False


async def test_an_arabic_body_verifies_through_the_endpoint(client: AsyncClient) -> None:
    """The vector that a re-serialising implementation fails."""

    body = '{"note":"المركز الأخضر — GH"}'.encode("utf-8")
    response = await client.post(VERIFY_PATH, json=_verification_payload(body=body))
    assert response.json()["valid"] is True


async def test_the_verification_endpoint_is_rate_limited(client: AsyncClient) -> None:
    limiter = FixedWindowRateLimiter(limit=2, window_seconds=60)
    app.dependency_overrides[get_aios_verification_rate_limiter] = lambda: limiter
    try:
        payload = _verification_payload()
        assert (await client.post(VERIFY_PATH, json=payload)).status_code == 200
        assert (await client.post(VERIFY_PATH, json=payload)).status_code == 200
        third = await client.post(VERIFY_PATH, json=payload)
        assert third.status_code == 429
    finally:
        app.dependency_overrides.pop(get_aios_verification_rate_limiter, None)


async def test_an_oversized_verification_payload_is_413(client: AsyncClient) -> None:
    payload = _verification_payload()
    payload["body_base64"] = base64.b64encode(b"x" * (64 * 1024 + 100)).decode("ascii")
    response = await client.post(
        VERIFY_PATH, content=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413


async def test_the_verification_endpoint_cannot_dispatch_a_workflow(
    client: AsyncClient, stub_client: StubClient
) -> None:
    """It verifies. It does not execute."""

    await client.post(VERIFY_PATH, json=_verification_payload())
    assert stub_client.dispatches == []


# ---------------------------------------------------------------------------
# Replay: deterministic and side-effect-free, by construction
# ---------------------------------------------------------------------------


async def test_a_replayed_verification_inside_the_window_is_accepted_again(
    client: AsyncClient,
) -> None:
    """Recorded deliberately: timestamp-only replay protection is
    acceptable ONLY because this workflow mutates nothing. The same
    request produces the same answer and no side effect. A mutating
    workflow requires persistent deduplication before approval -- see
    the Gate 1 protocol record."""

    payload = _verification_payload()
    first = await client.post(VERIFY_PATH, json=payload)
    second = await client.post(VERIFY_PATH, json=payload)
    assert first.json() == second.json()
    assert first.json()["valid"] is True


async def test_a_replay_outside_the_window_is_refused(client: AsyncClient) -> None:
    stale = _verification_payload(now=FIXED_NOW - timedelta(seconds=600))
    response = await client.post(VERIFY_PATH, json=stale)
    assert response.json()["valid"] is False


# ---------------------------------------------------------------------------
# The payload ceiling is enforced before the body is materialised
# ---------------------------------------------------------------------------


async def test_an_oversized_content_length_is_refused_on_the_public_route(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_client: StubClient,
) -> None:
    """A declared Content-Length over the ceiling is refused before the
    body is read into memory. The header is client-supplied and so is not
    trusted on its own -- the post-read check remains authoritative --
    but a hostile caller should not be able to force a large allocation
    just by declaring one."""

    headers = _sign_in(fake_verifier, fake_repository, role="admin")
    headers["Content-Type"] = "application/json"
    headers["Content-Length"] = str(64 * 1024 + 1)

    response = await client.post(INVOKE_PATH, headers=headers, content=b'{"input":{}}')

    assert response.status_code == 413
    assert stub_client.dispatches == []


async def test_an_oversized_content_length_is_refused_on_the_internal_route(
    client: AsyncClient,
) -> None:
    payload = json.dumps(_verification_payload()).encode()
    response = await client.post(
        VERIFY_PATH,
        content=payload,
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(64 * 1024 + 1),
        },
    )
    assert response.status_code == 413


async def test_a_malformed_content_length_falls_through_to_the_real_check(
    client: AsyncClient,
) -> None:
    """A garbage header must not be treated as a size decision, and must
    not crash the route -- the authoritative check is the actual length."""

    payload = json.dumps(_verification_payload()).encode()
    response = await client.post(
        VERIFY_PATH,
        content=payload,
        headers={"Content-Type": "application/json", "Content-Length": str(len(payload))},
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True


async def test_a_body_within_the_ceiling_is_accepted(
    client: AsyncClient, fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> None:
    headers = _sign_in(fake_verifier, fake_repository, role="admin")
    response = await client.post(INVOKE_PATH, headers=headers, json={"input": {}})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# A client cannot promote itself into an administrative role
# ---------------------------------------------------------------------------


FORGED_AUTHORITY_HEADERS = (
    {"X-Role": "admin"},
    {"X-Roles": "admin,owner"},
    {"X-User-Role": "owner"},
    {"X-Permission": "aios.invoke"},
    {"X-Permissions": "aios.invoke"},
    {"X-Is-Admin": "true"},
    {"Role": "admin"},
    {"X-Forwarded-Role": "owner"},
    {"X-Organization-Id": str(uuid.uuid4())},
    {"X-User-Id": str(uuid.uuid4())},
)


@pytest.mark.parametrize("forged", FORGED_AUTHORITY_HEADERS, ids=lambda h: next(iter(h)))
async def test_a_forged_role_header_cannot_grant_access(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_client: StubClient,
    forged: dict[str, str],
) -> None:
    """The decision reads only the server-resolved profile.

    An ``editor`` is authenticated and genuine -- only the *permission*
    is missing. Adding a header that claims otherwise must change
    nothing: ``require_permission`` consults ``resolve_trusted_role`` on
    the stored profile, and no request header participates.
    """

    headers = _sign_in(fake_verifier, fake_repository, role="editor")
    headers.update(forged)

    response = await client.post(INVOKE_PATH, headers=headers, json={"input": {}})

    assert response.status_code == 403
    assert stub_client.dispatches == [], "a forged header reached the orchestrator"


@pytest.mark.parametrize("forged", FORGED_AUTHORITY_HEADERS, ids=lambda h: next(iter(h)))
async def test_a_forged_role_header_cannot_rescue_an_unauthenticated_caller(
    client: AsyncClient, stub_client: StubClient, forged: dict[str, str]
) -> None:
    """Still 401 -- authentication is never satisfied by a claim."""

    response = await client.post(INVOKE_PATH, headers=forged, json={"input": {}})

    assert response.status_code == 401
    assert stub_client.dispatches == []


@pytest.mark.parametrize("claimed", ["admin", "owner"])
async def test_a_forged_role_in_the_payload_is_rejected_outright(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_client: StubClient,
    claimed: str,
) -> None:
    """A role claimed in the body is a forbidden authority field: refused
    by name with 422, never quietly ignored and never honoured."""

    headers = _sign_in(fake_verifier, fake_repository, role="admin")

    response = await client.post(
        INVOKE_PATH, headers=headers, json={"input": {"role": claimed}}
    )

    assert response.status_code == 422
    assert stub_client.dispatches == []


async def test_the_stored_profile_role_is_what_decides(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
) -> None:
    """The same request succeeds or fails purely on the stored role, with
    every other input held identical."""

    denied = _sign_in(fake_verifier, fake_repository, role="approver", token="t-approver")
    allowed = _sign_in(fake_verifier, fake_repository, role="admin", token="t-admin")

    assert (await client.post(INVOKE_PATH, headers=denied, json={"input": {}})).status_code == 403
    assert (await client.post(INVOKE_PATH, headers=allowed, json={"input": {}})).status_code == 200


async def test_the_health_check_route_still_declares_the_aios_permission() -> None:
    """The narrowing must not have detached the route from the policy.

    Read from the route's own dependency tree, not from a docstring: a
    route that lost ``require_permission`` would still pass every
    role-based test above by returning 200 to everyone.
    """

    from app.api.v1.aios import invoke_nora_health_check

    source = inspect.getsource(invoke_nora_health_check)
    assert "require_permission(Permission.AIOS_INVOKE)" in source
