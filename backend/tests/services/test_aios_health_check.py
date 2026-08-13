"""The NORA Health Check use case.

Two things are being proved. First, that the envelope this service builds
is exactly the signed contract -- actor context resolved server-side,
never accepted from anywhere else. Second, that everything the service
*could* have been given, it was not: it holds one dependency, and the
absence of the rest is asserted structurally rather than assumed.
"""

import ast
import inspect
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pytest

from app.core.exceptions import AuthorizationError
from app.domain.aios.client import (
    AIOSClient,
    AIOSDispatch,
    AIOSTimeoutError,
    AIOSUnavailableError,
    AIOSUnexpectedResponseError,
)
from app.domain.aios.contracts import CONTRACT_VERSION, AIOSStatus
from app.domain.aios.workflows import NORA_HEALTH_CHECK
from app.domain.entities.user import User
from app.services.aios.health_check import HealthCheckService

FIXED_NOW = datetime(2026, 8, 12, 14, 47, 5, tzinfo=timezone.utc)
FIXED_REQUEST_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
FIXED_CORRELATION_ID = uuid.UUID("7c9e6679-7425-40de-944b-e07fc1f90ae7")


class RecordingClient(AIOSClient):
    """Captures the dispatch and returns a scripted response."""

    def __init__(self, response: Mapping[str, Any] | None = None, error: Exception | None = None):
        self.dispatches: list[AIOSDispatch] = []
        self._response = response
        self._error = error

    async def invoke(self, dispatch: AIOSDispatch) -> Mapping[str, Any]:
        self.dispatches.append(dispatch)
        if self._error is not None:
            raise self._error
        return self._response or {}


_DEFAULT_ORGANIZATION = uuid.UUID("9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d")
#: Distinguishes "caller did not specify" from "caller specified None" --
#: an `or` default would quietly substitute an organization for the very
#: case that must prove one is absent.
_UNSET = object()


def _user(organization_id: Any = _UNSET) -> User:
    resolved = _DEFAULT_ORGANIZATION if organization_id is _UNSET else organization_id
    return User(
        id=uuid.UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6"),
        organization_id=resolved,
        full_name="Test User",
        email="test@example.com",
        role="admin",
        created_at=FIXED_NOW,
    )


def _ok_response(**overrides: Any) -> dict[str, Any]:
    body = {
        "contract_version": CONTRACT_VERSION,
        "request_id": str(FIXED_REQUEST_ID),
        "correlation_id": str(FIXED_CORRELATION_ID),
        "workflow": NORA_HEALTH_CHECK,
        "status": "completed",
        "output": {
            "service": "gh-aios",
            "orchestrator": "n8n",
            "role": "NORA",
            "health": "ok",
        },
        "metadata": {
            "execution_id": "1234",
            "workflow_version": "1.0.0",
            "started_at": "2026-08-12T14:47:05Z",
            "completed_at": "2026-08-12T14:47:05Z",
        },
    }
    body.update(overrides)
    return body


def _service(client: AIOSClient) -> HealthCheckService:
    return HealthCheckService(
        client, clock=lambda: FIXED_NOW, request_id_factory=lambda: FIXED_REQUEST_ID
    )


# ---------------------------------------------------------------------------
# The envelope
# ---------------------------------------------------------------------------


async def test_the_envelope_is_the_approved_contract() -> None:
    client = RecordingClient(_ok_response())
    await _service(client).invoke(_user(), correlation_id=FIXED_CORRELATION_ID)

    envelope = json.loads(client.dispatches[0].envelope_bytes)
    assert envelope == {
        "contract_version": "1.0",
        "request_id": str(FIXED_REQUEST_ID),
        "correlation_id": str(FIXED_CORRELATION_ID),
        "requested_at": "2026-08-12T14:47:05Z",
        "actor": {
            "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "organization_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        },
        "workflow": "nora.health_check",
        "input": {},
    }


async def test_actor_context_comes_from_the_trusted_profile() -> None:
    """Not from a parameter, and not from a payload -- the service has no
    way to accept one."""

    organization_id = uuid.uuid4()
    client = RecordingClient(_ok_response())
    await _service(client).invoke(
        _user(organization_id), correlation_id=FIXED_CORRELATION_ID
    )

    envelope = json.loads(client.dispatches[0].envelope_bytes)
    assert envelope["actor"]["organization_id"] == str(organization_id)


async def test_the_envelope_is_serialized_without_ascii_escaping() -> None:
    """Pinned because it is what makes the digest reproducible in
    JavaScript. ``ensure_ascii=True`` would escape non-ASCII to
    ``\\uXXXX`` and silently change the bytes that get signed."""

    client = RecordingClient(_ok_response())
    await _service(client).invoke(_user(), correlation_id=FIXED_CORRELATION_ID)

    raw = client.dispatches[0].envelope_bytes
    assert b"\\u" not in raw
    assert b", " not in raw and b": " not in raw, "compact separators"
    assert raw == raw.decode("utf-8").encode("utf-8")


async def test_a_user_without_an_organization_is_refused() -> None:
    """Fail closed. No default and no first-organization fallback."""

    client = RecordingClient(_ok_response())
    with pytest.raises(AuthorizationError):
        await _service(client).invoke(
            _user(organization_id=None), correlation_id=FIXED_CORRELATION_ID
        )
    assert client.dispatches == [], "nothing was dispatched"


async def test_the_request_id_is_server_generated_and_carried_into_the_dispatch() -> None:
    client = RecordingClient(_ok_response())
    result = await _service(client).invoke(_user(), correlation_id=FIXED_CORRELATION_ID)

    assert client.dispatches[0].request_id == FIXED_REQUEST_ID
    assert result.request_id == FIXED_REQUEST_ID


# ---------------------------------------------------------------------------
# The response
# ---------------------------------------------------------------------------


async def test_a_valid_response_is_returned() -> None:
    result = await _service(RecordingClient(_ok_response())).invoke(
        _user(), correlation_id=FIXED_CORRELATION_ID
    )

    assert result.status is AIOSStatus.COMPLETED
    assert result.workflow == NORA_HEALTH_CHECK
    assert result.output["health"] == "ok"
    assert result.metadata["workflow_version"] == "1.0.0"


async def test_identifiers_are_preserved_across_the_round_trip() -> None:
    result = await _service(RecordingClient(_ok_response())).invoke(
        _user(), correlation_id=FIXED_CORRELATION_ID
    )
    assert result.request_id == FIXED_REQUEST_ID
    assert result.correlation_id == FIXED_CORRELATION_ID


async def test_the_correlation_id_is_ours_not_the_echoed_one() -> None:
    """Adopting an upstream's copy would let a misrouted response
    silently rename this trace."""

    response = _ok_response(correlation_id=str(uuid.uuid4()))
    result = await _service(RecordingClient(response)).invoke(
        _user(), correlation_id=FIXED_CORRELATION_ID
    )
    assert result.correlation_id == FIXED_CORRELATION_ID


async def test_an_unrecognized_status_becomes_failed_not_completed() -> None:
    response = _ok_response(status="all-good")
    result = await _service(RecordingClient(response)).invoke(
        _user(), correlation_id=FIXED_CORRELATION_ID
    )
    assert result.status is AIOSStatus.FAILED


@pytest.mark.parametrize(
    "overrides",
    [
        {"contract_version": "2.0"},
        {"contract_version": None},
        {"request_id": str(uuid.uuid4())},
        {"workflow": "hafidh.master_inbox"},
    ],
    ids=["bad-version", "missing-version", "mismatched-request-id", "mismatched-workflow"],
)
async def test_a_response_about_a_different_request_is_refused(
    overrides: dict[str, Any]
) -> None:
    """A misrouted or replayed answer must never be reported as this
    caller's result."""

    with pytest.raises(AIOSUnexpectedResponseError):
        await _service(RecordingClient(_ok_response(**overrides))).invoke(
            _user(), correlation_id=FIXED_CORRELATION_ID
        )


@pytest.mark.parametrize(
    "overrides", [{"output": "not-an-object"}, {"metadata": 12}], ids=["output", "metadata"]
)
async def test_a_malformed_output_or_metadata_degrades_to_empty(
    overrides: dict[str, Any]
) -> None:
    result = await _service(RecordingClient(_ok_response(**overrides))).invoke(
        _user(), correlation_id=FIXED_CORRELATION_ID
    )
    assert result.output == {} or result.metadata == {}


@pytest.mark.parametrize(
    "error",
    [AIOSTimeoutError("t"), AIOSUnavailableError("u"), AIOSUnexpectedResponseError("x")],
    ids=["timeout", "unavailable", "unexpected"],
)
async def test_transport_errors_propagate_for_the_api_layer_to_map(
    error: Exception,
) -> None:
    with pytest.raises(type(error)):
        await _service(RecordingClient(error=error)).invoke(
            _user(), correlation_id=FIXED_CORRELATION_ID
        )


# ---------------------------------------------------------------------------
# Structural: the service cannot do what it was never given
# ---------------------------------------------------------------------------

_AIOS_SOURCE_FILES = (
    Path(__file__).resolve().parents[2] / "app" / "services" / "aios",
    Path(__file__).resolve().parents[2] / "app" / "api" / "v1" / "aios.py",
    Path(__file__).resolve().parents[2] / "app" / "api" / "v1" / "aios_internal.py",
    Path(__file__).resolve().parents[2] / "app" / "domain" / "aios",
)

#: Import prefixes that would give the AIOS layer a capability Gate 1
#: withheld. Asserted on the AST rather than by inspection, so a future
#: edit that reaches for one fails CI rather than being noticed in review.
_FORBIDDEN_IMPORT_PREFIXES = (
    "app.infrastructure.db",
    "app.infrastructure.repositories",
    "app.infrastructure.storage",
    "app.domain.repositories",
    "app.domain.storage",
    "app.domain.llm_gateway",
    "app.domain.embedding_provider",
    "app.infrastructure.ai",
    "app.services.evidence_review",
    "app.services.document_upload",
    "app.services.document_processing",
    "app.services.analysis",
    "app.services.vector_retrieval",
    "sqlalchemy",
    "asyncpg",
    "smtplib",
)


def _aios_modules() -> list[Path]:
    modules: list[Path] = []
    for target in _AIOS_SOURCE_FILES:
        if target.is_dir():
            modules.extend(sorted(target.rglob("*.py")))
        elif target.is_file():
            modules.append(target)
    return modules


def test_the_structural_guard_reads_the_real_modules() -> None:
    """A wrong path would make every assertion below pass vacuously."""

    names = {path.name for path in _aios_modules()}
    assert {"health_check.py", "request_verification.py", "aios.py", "aios_internal.py"} <= names


@pytest.mark.parametrize("module", _aios_modules(), ids=lambda p: p.name)
def test_no_aios_module_imports_a_database_or_provider(module: Path) -> None:
    """The health check touches no database, no storage, no model
    provider and no evidence command -- because none of them are
    reachable from here, not because nothing calls them."""

    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    for name in imported:
        for forbidden in _FORBIDDEN_IMPORT_PREFIXES:
            # Match on a module boundary, never a bare prefix: otherwise
            # `app.infrastructure.ai` would also match this layer's own
            # `app.infrastructure.aios`, and the guard would fail on
            # legitimate code while looking like a real finding.
            matches = name == forbidden or name.startswith(f"{forbidden}.")
            assert not matches, (
                f"{module.name} imports {name!r}, which would give the AIOS layer "
                f"a capability the foundation phase withholds"
            )


def test_the_health_check_service_holds_exactly_one_dependency() -> None:
    """One transport port. No repository, no session, no provider."""

    parameters = inspect.signature(HealthCheckService.__init__).parameters
    required = [
        name
        for name, parameter in parameters.items()
        if name != "self" and parameter.default is inspect.Parameter.empty
    ]
    assert required == ["client"]


def test_no_aios_module_can_reach_the_evidence_permission() -> None:
    """n8n may request a human decision; it may never record one."""

    for module in _aios_modules():
        source = module.read_text(encoding="utf-8")
        assert "EVIDENCE_REVIEW" not in source
        assert "EvidenceReviewService" not in source
