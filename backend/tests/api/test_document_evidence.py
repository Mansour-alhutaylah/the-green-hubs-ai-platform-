"""API-level tests for the four evidence-review endpoints.

Uses FastAPI's ``dependency_overrides`` to substitute a test-controlled
Supabase JWT verifier, an in-memory fake user repository (reusing
``test_auth.py``'s fakes, exactly like ``test_documents.py``), and a
stub ``EvidenceReviewService`` -- no network call to Supabase, no
database. The lifecycle rules themselves are covered exhaustively in
``tests/services/test_evidence_review_service.py`` and again against
real PostgreSQL in ``test_document_evidence_integration.py``; this file
exercises the router's own concerns: permission binding, request
validation, delegation, HTTP status mapping, and the response contract.

The allowed/denied role parametrization is **derived from
``ROLE_PERMISSIONS``**, never written out here, and so is the authorized
test identity itself (``authorized_headers``). The direction matters:
the policy is decided in ``app/domain/security/permissions.py`` and
pinned by ``tests/domain/security/test_permissions.py``; this file only
proves the routes enforce whatever that policy says. A hardcoded role
name here would let a test quietly become the place product authority
is defined -- and would keep passing if the policy changed underneath
it.

It also carries the **structural guards** for MVP Slice 4's central API
rule. Those guards draw a line that is easy to get wrong in either
direction:

* the five evidence *persistence columns* must never be writable
  through a generic document request model -- that is the state-machine
  bypass;
* but ``superseded_by_document_id`` is legitimate *command input* on
  the one controlled command that records a successor. Banning it
  everywhere would be wrong, and banning it nowhere would leave the
  bypass open. The guards below therefore check generic models and
  command models by different rules, and additionally pin which schema
  each route binds -- which is what proves a successor cannot be smuggled
  in through ``verify``, ``reject`` or ``restrict``.
"""

import importlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient
from pydantic import BaseModel

from app.api.deps import get_evidence_review_service, get_supabase_jwt_verifier, get_user_repository
from app.core.exceptions import (
    AuthorizationError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationError,
)
from app.domain.entities.document_evidence import DocumentEvidence
from app.domain.entities.user import User
from app.domain.evidence.lifecycle import MAX_REVIEW_REASON_CHARS, EvidenceStatus
from app.domain.security import Permission, Role, has_permission
from app.main import app
from app.schemas.document import (
    EvidenceReasonRequest,
    EvidenceSupersedeRequest,
    EvidenceVerifyRequest,
)

from tests.api.test_auth import FakeUserRepository, FakeVerifier

_ROUTER_DIR = Path(__file__).resolve().parents[2] / "app" / "api" / "v1"
_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "app" / "schemas"
_REPOSITORY_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "infrastructure"
    / "repositories"
    / "document.py"
)

#: The persisted columns of a recorded evidence decision. None of these
#: may be writable through a generic document request model.
#: ``review_reason`` is included because it is as much part of the
#: decision as the state: a client able to rewrite the justification for
#: a rejection could make a refusal read as something else entirely
#: without changing the state a status-only guard would be watching.
EVIDENCE_COLUMNS = (
    "evidence_status",
    "reviewed_by",
    "reviewed_at",
    "review_reason",
    "superseded_by_document_id",
)

#: Values whose authority is the server's alone. Unlike the columns
#: above, these may not appear on *any* request model, generic or
#: command: reviewer, timestamp and tenant are derived from the
#: authenticated profile and the database clock.
SERVER_AUTHORITATIVE_FIELDS = (
    "evidence_status",
    "reviewed_by",
    "reviewed_at",
    "organization_id",
)

#: The exact input each controlled command accepts. ``reason`` is
#: command input that becomes the persisted ``review_reason``;
#: ``superseded_by_document_id`` is accepted only where a successor is
#: meaningful.
EXPECTED_COMMAND_FIELDS: dict[type[BaseModel], set[str]] = {
    EvidenceVerifyRequest: {"reason"},
    EvidenceReasonRequest: {"reason"},
    EvidenceSupersedeRequest: {"reason", "superseded_by_document_id"},
}

#: Which request schema each route binds. This is what confines
#: ``superseded_by_document_id`` to ``supersede``.
EXPECTED_ROUTE_SCHEMAS = {
    "verify": "EvidenceVerifyRequest",
    "reject": "EvidenceReasonRequest",
    "restrict": "EvidenceReasonRequest",
    "supersede": "EvidenceSupersedeRequest",
}

COMMANDS = ("verify", "reject", "restrict", "supersede")
REASON_REQUIRED_COMMANDS = ("reject", "restrict", "supersede")

#: Derived from the live policy, not asserted here. See the module
#: docstring and
#: ``test_evidence_review_is_granted_to_exactly_the_documented_roles``.
REVIEW_CAPABLE_ROLES = tuple(
    sorted(role.value for role in Role if has_permission(role, Permission.EVIDENCE_REVIEW))
)
DENIED_KNOWN_ROLES = tuple(
    sorted(role.value for role in Role if not has_permission(role, Permission.EVIDENCE_REVIEW))
)
UNRECOGNIZED_ROLES = ("member", "superuser", "", None)


def _default_review_capable_role() -> str:
    """The authorized identity for tests that are not about roles.

    Resolved from the live policy at call time, with an explicit
    assertion, rather than indexed at import time -- an empty policy must
    fail with this message, not with an ``IndexError`` during
    collection."""

    assert REVIEW_CAPABLE_ROLES, "no role currently holds Permission.EVIDENCE_REVIEW"
    return REVIEW_CAPABLE_ROLES[0]


def _evidence(
    *,
    document_id: uuid.UUID | None = None,
    evidence_status: EvidenceStatus = EvidenceStatus.VERIFIED,
    reviewed_by: uuid.UUID | None = None,
    review_reason: str | None = None,
    superseded_by_document_id: uuid.UUID | None = None,
) -> DocumentEvidence:
    now = datetime.now(timezone.utc)
    return DocumentEvidence(
        document_id=document_id or uuid.uuid4(),
        engagement_id=uuid.uuid4(),
        evidence_status=evidence_status,
        processing_status="PROCESSED",
        reviewed_by=reviewed_by or uuid.uuid4(),
        reviewed_at=now,
        review_reason=review_reason,
        superseded_by_document_id=superseded_by_document_id,
        updated_at=now,
    )


class StubEvidenceReviewService:
    """Records each call so a *reached* service proves the router allowed
    it, and so the tests can assert what the router forwarded."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.result: DocumentEvidence | None = None

    def _respond(self, command: str, document_id: uuid.UUID, current_user: User, **kwargs):
        self.calls.append(
            {
                "command": command,
                "document_id": document_id,
                "current_user": current_user,
                **kwargs,
            }
        )
        if self.error is not None:
            raise self.error
        return self.result or _evidence(document_id=document_id)

    async def verify(self, document_id, current_user, *, reason=None):
        return self._respond("verify", document_id, current_user, reason=reason)

    async def reject(self, document_id, current_user, *, reason):
        return self._respond("reject", document_id, current_user, reason=reason)

    async def restrict(self, document_id, current_user, *, reason):
        return self._respond("restrict", document_id, current_user, reason=reason)

    async def supersede(
        self, document_id, current_user, *, reason, superseded_by_document_id=None
    ):
        return self._respond(
            "supersede",
            document_id,
            current_user,
            reason=reason,
            superseded_by_document_id=superseded_by_document_id,
        )


@pytest.fixture
def fake_repository() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def fake_verifier() -> FakeVerifier:
    return FakeVerifier()


@pytest.fixture
def stub_service() -> StubEvidenceReviewService:
    return StubEvidenceReviewService()


@pytest.fixture(autouse=True)
def _override_dependencies(
    fake_repository: FakeUserRepository,
    fake_verifier: FakeVerifier,
    stub_service: StubEvidenceReviewService,
):
    app.dependency_overrides[get_supabase_jwt_verifier] = lambda: fake_verifier
    app.dependency_overrides[get_user_repository] = lambda: fake_repository
    app.dependency_overrides[get_evidence_review_service] = lambda: stub_service
    yield
    for dependency in (
        get_supabase_jwt_verifier,
        get_user_repository,
        get_evidence_review_service,
    ):
        app.dependency_overrides.pop(dependency, None)


def _sign_in(
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    *,
    role: str | None,
    token: str = "valid-token",
) -> dict[str, str]:
    """Seed a trusted profile with ``role`` and return its bearer header.

    ``role`` is deliberately a *required* keyword with no default: the
    authorized identity comes from ``authorized_headers`` below, which
    derives it from the live policy."""

    user_id = uuid.uuid4()
    fake_verifier.register(token, user_id)
    fake_repository.seed(
        User(
            id=user_id,
            organization_id=uuid.uuid4(),
            full_name="Reviewer",
            email=f"reviewer-{user_id}@example.com",
            role=role,
            created_at=datetime.now(timezone.utc),
        )
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def authorized_headers(
    fake_verifier: FakeVerifier, fake_repository: FakeUserRepository
) -> dict[str, str]:
    """A caller who holds ``EVIDENCE_REVIEW`` according to the real
    policy -- whichever role that currently is."""

    return _sign_in(fake_verifier, fake_repository, role=_default_review_capable_role())


def _url(document_id: uuid.UUID, command: str) -> str:
    return f"/api/v1/documents/{document_id}/evidence/{command}"


def _body(command: str, **overrides: object) -> dict:
    body: dict = {} if command == "verify" else {"reason": "a recorded reason"}
    body.update(overrides)
    return body


# ---------------------------------------------------------------------------
# The derived parametrization must not be vacuous
# ---------------------------------------------------------------------------


def test_the_derived_role_sets_are_both_populated() -> None:
    """If the policy ever granted evidence review to every role, or to
    none, the parametrized tests below would silently stop proving
    anything. This makes that failure loud."""

    assert REVIEW_CAPABLE_ROLES, "no role holds EVIDENCE_REVIEW -- the routes are unreachable"
    assert DENIED_KNOWN_ROLES, "every role holds EVIDENCE_REVIEW -- denial is untested"
    assert set(REVIEW_CAPABLE_ROLES).isdisjoint(DENIED_KNOWN_ROLES)
    assert set(REVIEW_CAPABLE_ROLES) | set(DENIED_KNOWN_ROLES) == {role.value for role in Role}


# ---------------------------------------------------------------------------
# Authentication and authorization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", COMMANDS)
async def test_an_unauthenticated_review_is_401(
    client: AsyncClient, stub_service: StubEvidenceReviewService, command: str
) -> None:
    response = await client.post(_url(uuid.uuid4(), command), json=_body(command))

    assert response.status_code == 401
    assert stub_service.calls == []


@pytest.mark.parametrize("role", DENIED_KNOWN_ROLES)
@pytest.mark.parametrize("command", COMMANDS)
async def test_a_role_without_the_permission_is_denied(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubEvidenceReviewService,
    role: str,
    command: str,
) -> None:
    """Deny by default, and deny *before* the service: a role the policy
    does not grant ``evidence.review`` must not be able to approve
    evidence by calling the API directly, whatever the UI shows."""

    headers = _sign_in(fake_verifier, fake_repository, role=role)

    response = await client.post(_url(uuid.uuid4(), command), headers=headers, json=_body(command))

    assert response.status_code == 403
    assert stub_service.calls == []


@pytest.mark.parametrize("role", UNRECOGNIZED_ROLES)
@pytest.mark.parametrize("command", COMMANDS)
async def test_an_unrecognized_or_missing_role_is_denied(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubEvidenceReviewService,
    role: str | None,
    command: str,
) -> None:
    headers = _sign_in(fake_verifier, fake_repository, role=role)

    response = await client.post(_url(uuid.uuid4(), command), headers=headers, json=_body(command))

    assert response.status_code == 403
    assert stub_service.calls == []


@pytest.mark.parametrize("role", REVIEW_CAPABLE_ROLES)
@pytest.mark.parametrize("command", COMMANDS)
async def test_a_role_holding_the_permission_reaches_the_service(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubEvidenceReviewService,
    role: str,
    command: str,
) -> None:
    headers = _sign_in(fake_verifier, fake_repository, role=role)

    response = await client.post(_url(uuid.uuid4(), command), headers=headers, json=_body(command))

    assert response.status_code == 200
    assert stub_service.calls[0]["command"] == command


@pytest.mark.parametrize("command", COMMANDS)
async def test_a_forged_permission_header_is_ignored(
    client: AsyncClient,
    fake_verifier: FakeVerifier,
    fake_repository: FakeUserRepository,
    stub_service: StubEvidenceReviewService,
    command: str,
) -> None:
    """Authorization reads the server-stored profile only."""

    headers = _sign_in(fake_verifier, fake_repository, role=DENIED_KNOWN_ROLES[0])
    headers.update({"X-Permission": "evidence.review", "Role": "owner"})

    response = await client.post(_url(uuid.uuid4(), command), headers=headers, json=_body(command))

    assert response.status_code == 403
    assert stub_service.calls == []


# ---------------------------------------------------------------------------
# Server-derived authority: the client supplies none of it
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", COMMANDS)
async def test_client_supplied_reviewer_organization_and_timestamp_are_ignored(
    client: AsyncClient,
    authorized_headers: dict[str, str],
    stub_service: StubEvidenceReviewService,
    command: str,
) -> None:
    """The authoritative values have no request field at all, so a
    client that sends them anyway changes nothing -- the unknown keys are
    dropped and the service is called with the trusted user only."""

    body = _body(
        command,
        reviewed_by=str(uuid.uuid4()),
        reviewed_at="2020-01-01T00:00:00Z",
        organization_id=str(uuid.uuid4()),
        evidence_status="VERIFIED",
    )

    response = await client.post(_url(uuid.uuid4(), command), headers=authorized_headers, json=body)

    assert response.status_code == 200
    call = stub_service.calls[0]
    assert set(call) <= {
        "command",
        "document_id",
        "current_user",
        "reason",
        "superseded_by_document_id",
    }
    for forged in SERVER_AUTHORITATIVE_FIELDS:
        assert forged not in call


@pytest.mark.parametrize("command", ["verify", "reject", "restrict"])
async def test_a_successor_cannot_be_smuggled_into_a_non_supersede_command(
    client: AsyncClient,
    authorized_headers: dict[str, str],
    stub_service: StubEvidenceReviewService,
    command: str,
) -> None:
    """Only ``supersede`` records a successor. The other three bind
    schemas without the field, so it is dropped rather than forwarded."""

    body = _body(command, superseded_by_document_id=str(uuid.uuid4()))

    response = await client.post(_url(uuid.uuid4(), command), headers=authorized_headers, json=body)

    assert response.status_code == 200
    assert "superseded_by_document_id" not in stub_service.calls[0]


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------


async def test_verify_accepts_an_absent_body(
    client: AsyncClient,
    authorized_headers: dict[str, str],
    stub_service: StubEvidenceReviewService,
) -> None:
    response = await client.post(_url(uuid.uuid4(), "verify"), headers=authorized_headers)

    assert response.status_code == 200
    assert stub_service.calls[0]["reason"] is None


async def test_verify_accepts_an_optional_note(
    client: AsyncClient,
    authorized_headers: dict[str, str],
    stub_service: StubEvidenceReviewService,
) -> None:
    response = await client.post(
        _url(uuid.uuid4(), "verify"), headers=authorized_headers, json={"reason": "totals checked"}
    )

    assert response.status_code == 200
    assert stub_service.calls[0]["reason"] == "totals checked"


@pytest.mark.parametrize("command", REASON_REQUIRED_COMMANDS)
async def test_a_missing_reason_is_422(
    client: AsyncClient,
    authorized_headers: dict[str, str],
    stub_service: StubEvidenceReviewService,
    command: str,
) -> None:
    response = await client.post(_url(uuid.uuid4(), command), headers=authorized_headers, json={})

    assert response.status_code == 422
    assert stub_service.calls == []


@pytest.mark.parametrize("command", REASON_REQUIRED_COMMANDS)
@pytest.mark.parametrize("reason", ["", "   ", "\t\n ", None])
async def test_a_blank_or_null_reason_is_422(
    client: AsyncClient,
    authorized_headers: dict[str, str],
    stub_service: StubEvidenceReviewService,
    command: str,
    reason: str | None,
) -> None:
    """Whitespace-only is rejected as firmly as omitted -- padding a
    required justification with spaces must not satisfy it."""

    response = await client.post(
        _url(uuid.uuid4(), command), headers=authorized_headers, json={"reason": reason}
    )

    assert response.status_code == 422
    assert stub_service.calls == []


@pytest.mark.parametrize("command", REASON_REQUIRED_COMMANDS)
async def test_an_over_long_reason_is_422(
    client: AsyncClient,
    authorized_headers: dict[str, str],
    stub_service: StubEvidenceReviewService,
    command: str,
) -> None:
    response = await client.post(
        _url(uuid.uuid4(), command),
        headers=authorized_headers,
        json={"reason": "x" * (MAX_REVIEW_REASON_CHARS + 1)},
    )

    assert response.status_code == 422
    assert stub_service.calls == []


@pytest.mark.parametrize("command", REASON_REQUIRED_COMMANDS)
async def test_a_reason_at_the_bound_is_accepted(
    client: AsyncClient, authorized_headers: dict[str, str], command: str
) -> None:
    response = await client.post(
        _url(uuid.uuid4(), command),
        headers=authorized_headers,
        json={"reason": "x" * MAX_REVIEW_REASON_CHARS},
    )

    assert response.status_code == 200


async def test_an_over_long_verify_note_is_422(
    client: AsyncClient,
    authorized_headers: dict[str, str],
    stub_service: StubEvidenceReviewService,
) -> None:
    response = await client.post(
        _url(uuid.uuid4(), "verify"),
        headers=authorized_headers,
        json={"reason": "x" * (MAX_REVIEW_REASON_CHARS + 1)},
    )

    assert response.status_code == 422
    assert stub_service.calls == []


async def test_supersede_forwards_an_optional_successor(
    client: AsyncClient,
    authorized_headers: dict[str, str],
    stub_service: StubEvidenceReviewService,
) -> None:
    successor = uuid.uuid4()

    response = await client.post(
        _url(uuid.uuid4(), "supersede"),
        headers=authorized_headers,
        json={"reason": "replaced", "superseded_by_document_id": str(successor)},
    )

    assert response.status_code == 200
    assert stub_service.calls[0]["superseded_by_document_id"] == successor


async def test_supersede_without_a_successor_is_accepted(
    client: AsyncClient,
    authorized_headers: dict[str, str],
    stub_service: StubEvidenceReviewService,
) -> None:
    response = await client.post(
        _url(uuid.uuid4(), "supersede"), headers=authorized_headers, json={"reason": "obsolete"}
    )

    assert response.status_code == 200
    assert stub_service.calls[0]["superseded_by_document_id"] is None


async def test_a_malformed_successor_id_is_422(
    client: AsyncClient,
    authorized_headers: dict[str, str],
    stub_service: StubEvidenceReviewService,
) -> None:
    response = await client.post(
        _url(uuid.uuid4(), "supersede"),
        headers=authorized_headers,
        json={"reason": "replaced", "superseded_by_document_id": "not-a-uuid"},
    )

    assert response.status_code == 422
    assert stub_service.calls == []


@pytest.mark.parametrize("command", COMMANDS)
async def test_a_malformed_document_id_is_422(
    client: AsyncClient,
    authorized_headers: dict[str, str],
    stub_service: StubEvidenceReviewService,
    command: str,
) -> None:
    response = await client.post(
        f"/api/v1/documents/not-a-uuid/evidence/{command}",
        headers=authorized_headers,
        json=_body(command),
    )

    assert response.status_code == 422
    assert stub_service.calls == []


# ---------------------------------------------------------------------------
# HTTP error mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (AuthorizationError("User has no organization"), 403),
        (NotFoundError("Document not found"), 404),
        (InvalidStateTransitionError("Document evidence status is REJECTED"), 409),
        (ValidationError("A document cannot supersede itself"), 422),
    ],
)
async def test_domain_errors_map_to_deterministic_statuses(
    client: AsyncClient,
    authorized_headers: dict[str, str],
    stub_service: StubEvidenceReviewService,
    command: str,
    error: Exception,
    expected_status: int,
) -> None:
    stub_service.error = error

    response = await client.post(
        _url(uuid.uuid4(), command), headers=authorized_headers, json=_body(command)
    )

    assert response.status_code == expected_status
    assert set(response.json()) == {"detail"}


@pytest.mark.parametrize("command", COMMANDS)
async def test_an_error_body_leaks_no_internals(
    client: AsyncClient,
    authorized_headers: dict[str, str],
    stub_service: StubEvidenceReviewService,
    command: str,
) -> None:
    """A conflict may name the current state -- the caller owns the
    document -- but never SQL, predicates, or a stack trace."""

    stub_service.error = InvalidStateTransitionError(
        "Document evidence status is REJECTED; a verify decision is not permitted from that state."
    )

    response = await client.post(
        _url(uuid.uuid4(), command), headers=authorized_headers, json=_body(command)
    )

    body = response.text.lower()
    for leaked in ("select ", "update ", "where ", "organization_id =", "traceback", "engagements"):
        assert leaked not in body


@pytest.mark.parametrize("command", COMMANDS)
async def test_no_error_message_reports_a_missing_none_successor(
    client: AsyncClient,
    authorized_headers: dict[str, str],
    stub_service: StubEvidenceReviewService,
    command: str,
) -> None:
    """Regression pin for the nonsense ``Document None not found``."""

    stub_service.error = InvalidStateTransitionError(
        "The evidence decision could not be applied because the document changed "
        "concurrently; reload the current state and retry."
    )

    response = await client.post(
        _url(uuid.uuid4(), command), headers=authorized_headers, json=_body(command)
    )

    assert response.status_code == 409
    assert "none not found" not in response.text.lower()


# ---------------------------------------------------------------------------
# Response contract
# ---------------------------------------------------------------------------


async def test_the_evidence_response_contract(
    client: AsyncClient,
    authorized_headers: dict[str, str],
    stub_service: StubEvidenceReviewService,
) -> None:
    document_id = uuid.uuid4()
    successor = uuid.uuid4()
    reviewer_id = uuid.uuid4()
    stub_service.result = _evidence(
        document_id=document_id,
        evidence_status=EvidenceStatus.SUPERSEDED,
        reviewed_by=reviewer_id,
        review_reason="replaced by the FY25 restatement",
        superseded_by_document_id=successor,
    )

    response = await client.post(
        _url(document_id, "supersede"),
        headers=authorized_headers,
        json={"reason": "replaced by the FY25 restatement"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "id",
        "engagement_id",
        "evidence_status",
        "processing_status",
        "reviewed_by",
        "reviewed_at",
        "review_reason",
        "superseded_by_document_id",
        "updated_at",
    }
    assert body["id"] == str(document_id)
    assert body["evidence_status"] == "SUPERSEDED"
    assert body["reviewed_by"] == str(reviewer_id)
    assert body["superseded_by_document_id"] == str(successor)
    # Internal storage details never travel on an evidence response.
    assert "storage_path" not in body
    assert "filename" not in body


# ---------------------------------------------------------------------------
# Structural guard: generic document mutation cannot touch evidence
# ---------------------------------------------------------------------------


def _request_models() -> dict[str, type[BaseModel]]:
    """Every Pydantic *request* model in the whole ``app.schemas``
    package.

    Every module is imported, not just ``document``: scanning one module
    would make the generic-model guard below pass vacuously today (that
    module's only ``*Request`` classes are the three evidence commands),
    and would miss a ``DocumentUpdateRequest`` added anywhere else."""

    models: dict[str, type[BaseModel]] = {}
    for path in sorted(_SCHEMA_DIR.glob("*.py")):
        if path.stem == "__init__":
            continue
        module = importlib.import_module(f"app.schemas.{path.stem}")
        for name in dir(module):
            candidate = getattr(module, name)
            if (
                isinstance(candidate, type)
                and issubclass(candidate, BaseModel)
                and name.endswith("Request")
            ):
                models[f"{path.stem}.{name}"] = candidate
    return models


def _generic_request_models() -> dict[str, type[BaseModel]]:
    """Request models that are *not* one of the controlled evidence
    commands -- every other body a client can post anywhere in the API,
    plus any generic document create/update body added in future."""

    command_models = {model.__name__ for model in EXPECTED_COMMAND_FIELDS}
    return {
        name: model
        for name, model in _request_models().items()
        if model.__name__ not in command_models
    }


def test_the_generic_request_model_scan_is_not_empty() -> None:
    """The guard below asserts an absence; if the scan found nothing it
    would assert that absence over nothing at all."""

    generic = _generic_request_models()

    assert generic, "no generic request models found -- the scan is broken"
    # A model that genuinely exists today, so a broken import path fails here.
    assert any(name.endswith("EngagementUpdateRequest") for name in generic)


def test_the_router_exposes_no_generic_document_patch_or_put() -> None:
    """A generic document update is the bypass this slice must not have:
    it would let a client name any target state, skipping the matrix,
    the reason rules and the processing precondition alike."""

    source = (_ROUTER_DIR / "documents.py").read_text(encoding="utf-8")

    assert "@router.patch" not in source
    assert "@router.put" not in source


@pytest.mark.parametrize("column", EVIDENCE_COLUMNS)
def test_no_generic_document_request_model_accepts_an_evidence_column(column: str) -> None:
    """The five persisted evidence columns are writable only through the
    controlled transition. A generic body carrying one of them would be
    a state-machine bypass regardless of the route wrapping it."""

    offenders = [
        f"{name}.{column}"
        for name, model in _generic_request_models().items()
        if column in model.model_fields
    ]

    assert offenders == [], f"generic request model(s) accept a client-supplied {column}: {offenders}"


@pytest.mark.parametrize("column", EVIDENCE_COLUMNS)
def test_no_schema_module_declares_a_generic_document_update_with_an_evidence_column(
    column: str,
) -> None:
    """Source-level companion to the runtime check above, covering every
    schema module rather than only ``document.py`` -- a
    ``DocumentUpdateRequest`` added in another module would otherwise be
    invisible to it."""

    command_models = {model.__name__ for model in EXPECTED_COMMAND_FIELDS}
    offenders: list[str] = []
    for path in sorted(_SCHEMA_DIR.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for block in re.split(r"\nclass ", source):
            name = block.split("(", 1)[0].strip()
            if not name.endswith("Request") or name in command_models:
                continue
            if re.search(rf"^\s+{column}\s*:", block, re.MULTILINE):
                offenders.append(f"{path.name}:{name}")

    assert offenders == [], f"generic request schema(s) accept {column}: {offenders}"


def test_the_generic_document_update_writes_no_evidence_column() -> None:
    """``documents``' evidence columns must be written by the repository's
    one conditional transition statement, never by the generic
    ``update()`` the ORM offers."""

    source = _REPOSITORY_SOURCE.read_text(encoding="utf-8")
    generic_update = source.split("    async def update(")[1].split("    async def")[0]

    for column in EVIDENCE_COLUMNS:
        assert column not in generic_update, (
            f"the generic Document update() writes {column}; evidence state must "
            "only change through transition_evidence()"
        )


# ---------------------------------------------------------------------------
# Structural guard: the command schemas accept only their own input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "expected"), [(model, fields) for model, fields in EXPECTED_COMMAND_FIELDS.items()]
)
def test_each_command_schema_accepts_exactly_its_intended_fields(
    model: type[BaseModel], expected: set[str]
) -> None:
    assert set(model.model_fields) == expected, (
        f"{model.__name__} accepts unexpected input: "
        f"{set(model.model_fields).symmetric_difference(expected)}"
    )


@pytest.mark.parametrize("model", list(EXPECTED_COMMAND_FIELDS))
@pytest.mark.parametrize("field", SERVER_AUTHORITATIVE_FIELDS)
def test_no_command_schema_accepts_a_server_authoritative_field(
    model: type[BaseModel], field: str
) -> None:
    """Reviewer, timestamp, tenant and target state are the server's to
    decide. The absence of the fields is what makes supplying them
    impossible rather than merely ignored."""

    assert field not in model.model_fields


def test_only_the_supersede_schema_accepts_a_successor() -> None:
    """``superseded_by_document_id`` is legitimate command input -- but on
    exactly one command."""

    assert "superseded_by_document_id" in EvidenceSupersedeRequest.model_fields
    assert "superseded_by_document_id" not in EvidenceVerifyRequest.model_fields
    assert "superseded_by_document_id" not in EvidenceReasonRequest.model_fields


def test_the_reason_is_optional_only_for_verify() -> None:
    assert EvidenceVerifyRequest.model_fields["reason"].is_required() is False
    assert EvidenceReasonRequest.model_fields["reason"].is_required() is True
    assert EvidenceSupersedeRequest.model_fields["reason"].is_required() is True


def test_the_successor_is_optional_on_supersede() -> None:
    """A reviewer may mark a document obsolete with no replacement."""

    assert EvidenceSupersedeRequest.model_fields["superseded_by_document_id"].is_required() is False


# ---------------------------------------------------------------------------
# Structural guard: every route is bound to its permission and its schema
# ---------------------------------------------------------------------------


def _evidence_route_declarations() -> list[tuple[str, str]]:
    """Return ``(path, decorator + handler signature)`` per evidence route.

    Captures through to the end of the handler signature so both the
    bound request schema and the permission dependency -- which sits on
    the handler's ``current_user`` parameter, not in the decorator -- are
    inside the captured text."""

    source = (_ROUTER_DIR / "documents.py").read_text(encoding="utf-8")
    return re.findall(
        r'@router\.post\(\s*"(/\{document_id\}/evidence/[a-z]+)".*?\)\s*'
        r"async def \w+\((.*?)\n\) ->",
        source,
        re.DOTALL,
    )


def test_the_route_scan_finds_all_four_routes() -> None:
    """A regex that silently matched nothing would make the guards below
    pass by asserting over an empty list."""

    declarations = _evidence_route_declarations()

    assert len(declarations) == len(COMMANDS)
    assert {path for path, _ in declarations} == {
        f"/{{document_id}}/evidence/{command}" for command in COMMANDS
    }


def test_every_evidence_route_is_individually_permission_bound() -> None:
    """Per-route, not a source-wide count: a global count would stay
    green if one route lost its binding while the same text appeared
    twice somewhere else in the file."""

    for path, declaration in _evidence_route_declarations():
        assert "require_permission(Permission.EVIDENCE_REVIEW)" in declaration, (
            f"{path} is missing the EVIDENCE_REVIEW permission binding"
        )
        bound = re.findall(r"require_permission\(Permission\.(\w+)\)", declaration)
        assert bound == ["EVIDENCE_REVIEW"], f"{path} binds unexpected permission(s): {bound}"


def test_every_evidence_route_binds_its_intended_request_schema() -> None:
    """This is what confines ``superseded_by_document_id`` to the
    supersede command: the other three routes parse bodies with schemas
    that have no such field."""

    for path, declaration in _evidence_route_declarations():
        command = path.rsplit("/", 1)[1]
        expected_schema = EXPECTED_ROUTE_SCHEMAS[command]
        assert expected_schema in declaration, (
            f"{path} does not bind {expected_schema}"
        )
