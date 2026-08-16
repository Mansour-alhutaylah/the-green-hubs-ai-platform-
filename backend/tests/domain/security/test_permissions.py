"""Focused tests for the permission catalog and role policy.

Pure unit tests: no FastAPI, no database, no network. They pin the
fail-closed contract that the route layer depends on.
"""

import re
import socket
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.domain.entities.user import User
from app.domain.security import (
    ROLE_PERMISSIONS,
    Permission,
    Role,
    has_permission,
    permissions_for_role,
    resolve_trusted_role,
)

_ADMIN_CLASS_PERMISSIONS = frozenset({Permission.ORGANIZATION_MANAGE})
_ROLES_TS = (
    Path(__file__).resolve().parents[3].parent
    / "frontend"
    / "src"
    / "features"
    / "rbac"
    / "roles.ts"
)


def _user(role: object) -> User:
    return User(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        full_name="Test User",
        email="test@example.com",
        role=role,  # type: ignore[arg-type]
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Catalog completeness
# ---------------------------------------------------------------------------


def test_every_role_has_an_explicit_permission_set() -> None:
    for role in Role:
        assert role in ROLE_PERMISSIONS, f"{role} has no explicit policy entry"


def test_backend_roles_match_the_frontend_role_vocabulary() -> None:
    """Guards backlog A-1: the UI tiers and the server policy must not drift."""

    source = _ROLES_TS.read_text(encoding="utf-8")
    block = source.split("export const Role = {", 1)[1].split("} as const;", 1)[0]
    frontend_roles = set(re.findall(r"'([a-z]+)'", block))
    assert frontend_roles == {role.value for role in Role}


# ---------------------------------------------------------------------------
# Fail-closed behaviour
# ---------------------------------------------------------------------------


def test_missing_role_is_denied_every_permission() -> None:
    assert resolve_trusted_role(_user(None)) is None
    for permission in Permission:
        assert has_permission(None, permission) is False


@pytest.mark.parametrize("raw", ["member", "superuser", "", "  ", "admin ; drop", 42, None])
def test_unrecognized_role_values_resolve_to_none(raw: object) -> None:
    assert resolve_trusted_role(_user(raw)) is None


def test_unknown_role_is_denied_every_permission() -> None:
    unknown = resolve_trusted_role(_user("member"))
    for permission in Permission:
        assert has_permission(unknown, permission) is False


@pytest.mark.parametrize("unknown", ["document.destroy", "organization.*", "*", ""])
def test_unknown_permission_is_denied_even_for_the_highest_role(unknown: str) -> None:
    assert has_permission(Role.OWNER, unknown) is False


def test_permissions_for_an_unknown_role_is_empty() -> None:
    assert permissions_for_role(None) == frozenset()


# ---------------------------------------------------------------------------
# Least privilege
# ---------------------------------------------------------------------------


def test_viewer_holds_no_permission_at_all() -> None:
    assert permissions_for_role(Role.VIEWER) == frozenset()


@pytest.mark.parametrize("permission", list(Permission))
def test_viewer_is_denied_every_catalogued_permission(permission: Permission) -> None:
    assert has_permission(Role.VIEWER, permission) is False


@pytest.mark.parametrize("role", [Role.VIEWER, Role.EDITOR, Role.APPROVER])
def test_non_administrative_roles_do_not_hold_administrative_permissions(role: Role) -> None:
    assert permissions_for_role(role).isdisjoint(_ADMIN_CLASS_PERMISSIONS)


@pytest.mark.parametrize("role", [Role.ADMIN, Role.OWNER])
def test_administrative_roles_hold_the_administrative_permission(role: Role) -> None:
    assert Permission.ORGANIZATION_MANAGE in permissions_for_role(role)


def test_write_capable_roles_can_upload_a_document() -> None:
    for role in (Role.EDITOR, Role.APPROVER, Role.ADMIN, Role.OWNER):
        assert has_permission(role, Permission.DOCUMENT_UPLOAD) is True


def test_evidence_review_is_granted_to_exactly_the_documented_roles() -> None:
    """The authoritative pin for MVP Slice 4's authorization policy.

    This assertion -- not any API test -- is where the evidence-review
    role mapping is decided; ``test_document_evidence.py`` derives its
    allowed/denied parametrization from ``ROLE_PERMISSIONS`` so that the
    tests follow the policy rather than establish it.

    The mapping grants ``evidence.review`` to every role that already
    holds write permissions, and to no other. That is deliberately the
    coarsest split that closes the property Slice 4 needs -- a
    ``viewer`` cannot approve evidence, withdraw an approval, or make a
    document retrievable -- without inventing the approver/editor
    distinction that management decision **M-4** owns and that backlog
    risk R-1 forbids engineering from inventing.

    **This assertion is expected to change when M-4 lands**, and the
    change is one line in ``ROLE_PERMISSIONS`` plus one line here."""

    granted = {role for role in Role if Permission.EVIDENCE_REVIEW in permissions_for_role(role)}

    assert granted == {Role.EDITOR, Role.APPROVER, Role.ADMIN, Role.OWNER}
    assert Role.VIEWER not in granted


def test_evidence_review_is_not_administrative() -> None:
    """Reviewing evidence is not an organization-management action; it
    must not have been folded into the admin-class set."""

    assert Permission.EVIDENCE_REVIEW not in _ADMIN_CLASS_PERMISSIONS
    assert has_permission(Role.APPROVER, Permission.EVIDENCE_REVIEW) is True
    assert has_permission(Role.APPROVER, Permission.ORGANIZATION_MANAGE) is False


def test_role_resolution_normalizes_case_and_surrounding_whitespace() -> None:
    assert resolve_trusted_role(_user("  Admin ")) is Role.ADMIN


# ---------------------------------------------------------------------------
# Immutability and determinism
# ---------------------------------------------------------------------------


def test_the_policy_mapping_cannot_be_reassigned_at_runtime() -> None:
    with pytest.raises(TypeError):
        ROLE_PERMISSIONS[Role.VIEWER] = frozenset(Permission)  # type: ignore[index]


def test_individual_permission_sets_cannot_be_mutated() -> None:
    granted = permissions_for_role(Role.VIEWER)
    assert isinstance(granted, frozenset)
    with pytest.raises(AttributeError):
        granted.add(Permission.DOCUMENT_UPLOAD)  # type: ignore[attr-defined]


def test_repeated_evaluation_is_deterministic() -> None:
    first = [has_permission(Role.EDITOR, p) for p in Permission]
    second = [has_permission(Role.EDITOR, p) for p in Permission]
    assert first == second


def test_permission_evaluation_opens_no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    """No LLM, model provider or other network call may gate a decision."""

    def _forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("permission evaluation attempted a network call")

    monkeypatch.setattr(socket, "socket", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)

    assert has_permission(Role.ADMIN, Permission.DOCUMENT_UPLOAD) is True
    assert has_permission(Role.VIEWER, Permission.DOCUMENT_UPLOAD) is False
    assert resolve_trusted_role(_user("owner")) is Role.OWNER


# ---------------------------------------------------------------------------
# AIOS orchestration (Gate 3)
# ---------------------------------------------------------------------------


def test_aios_invoke_is_catalogued() -> None:
    assert Permission.AIOS_INVOKE.value == "aios.invoke"


def test_a_viewer_may_not_invoke_orchestration() -> None:
    """The same property Slice 2 closed for uploads: a read-only role
    cannot reach a write-shaped capability by calling the API directly."""

    assert has_permission(Role.VIEWER, Permission.AIOS_INVOKE) is False


#: The complete, recorded answer for this phase. Stated once, here, and
#: derived from :data:`Role` so a future role added to the enum without a
#: decision fails :func:`test_every_role_is_classified_for_aios_invoke`
#: rather than silently defaulting to denied-and-untested.
AIOS_ALLOWED_ROLES: frozenset[Role] = frozenset({Role.ADMIN, Role.OWNER})
AIOS_DENIED_ROLES: frozenset[Role] = frozenset(Role) - AIOS_ALLOWED_ROLES


@pytest.mark.parametrize("role", sorted(AIOS_ALLOWED_ROLES, key=lambda r: r.value))
def test_administrative_roles_may_invoke_orchestration(role: Role) -> None:
    """Admin and Owner only.

    NORA is a Founder/administrative capability this phase, and
    ``aios.invoke`` is a *generic* orchestration permission that will
    gate more capable workflows later -- so it is granted narrowly now
    rather than widened silently the day those workflows are registered.
    """

    assert has_permission(role, Permission.AIOS_INVOKE) is True


@pytest.mark.parametrize("role", sorted(AIOS_DENIED_ROLES, key=lambda r: r.value))
def test_non_administrative_roles_may_not_invoke_orchestration(role: Role) -> None:
    """Viewer, Editor and Approver are each denied, individually.

    Editor and Approver are named explicitly because they *were* granted
    this permission before the reviewer decision -- a regression here
    would be a silent re-widening, which is exactly the failure this
    parametrization exists to catch.
    """

    assert has_permission(role, Permission.AIOS_INVOKE) is False


def test_every_role_is_classified_for_aios_invoke() -> None:
    """No role may be left unclassified. A new member of :class:`Role`
    added without a recorded decision fails here."""

    assert AIOS_ALLOWED_ROLES | AIOS_DENIED_ROLES == frozenset(Role)
    assert not (AIOS_ALLOWED_ROLES & AIOS_DENIED_ROLES)


def test_the_policy_itself_grants_aios_invoke_to_exactly_two_roles() -> None:
    """Read from ``ROLE_PERMISSIONS`` rather than from the constants
    above, so the test and the policy cannot drift together."""

    granting = {
        role
        for role, permissions in ROLE_PERMISSIONS.items()
        if Permission.AIOS_INVOKE in permissions
    }
    assert granting == {Role.ADMIN, Role.OWNER}


def test_aios_invoke_is_a_distinct_permission_from_evidence_review() -> None:
    """Holding ``aios.invoke`` confers no authority over evidence. n8n may
    request a human decision; it may never record one."""

    assert Permission.AIOS_INVOKE is not Permission.EVIDENCE_REVIEW
    assert Permission.AIOS_INVOKE.value != Permission.EVIDENCE_REVIEW.value


def test_the_aios_grant_did_not_widen_any_other_permission() -> None:
    """Adding a permission must not silently hand a role something else.
    Viewer in particular must still hold nothing at all."""

    assert permissions_for_role(Role.VIEWER) == frozenset()
    assert Permission.ORGANIZATION_MANAGE not in permissions_for_role(Role.EDITOR)
    assert Permission.ORGANIZATION_MANAGE not in permissions_for_role(Role.APPROVER)


def test_narrowing_aios_invoke_changed_no_other_permission() -> None:
    """Pins every non-AIOS grant to what it was before the narrowing.

    The correction had to remove one permission from two roles and touch
    nothing else. Comparing the full sets with ``aios.invoke`` factored
    out is what proves that -- a test that only checked ``aios.invoke``
    would not notice a neighbouring permission lost in the same edit.

    The expectations are written out literally rather than rebuilt from
    the module's own private constants: reusing ``_WRITE_PERMISSIONS``
    here would make the assertion tautological, since a mistaken edit to
    that constant would move the test and the policy together.
    """

    write_and_review = frozenset(
        {
            Permission.ENGAGEMENT_MANAGE,
            Permission.DOCUMENT_UPLOAD,
            Permission.DOCUMENT_PROCESS,
            Permission.ANALYSIS_RUN,
            Permission.EVIDENCE_REVIEW,
        }
    )
    expected_without_aios = {
        Role.VIEWER: frozenset(),
        Role.EDITOR: write_and_review,
        Role.APPROVER: write_and_review,
        Role.ADMIN: write_and_review | {Permission.ORGANIZATION_MANAGE},
        Role.OWNER: write_and_review | {Permission.ORGANIZATION_MANAGE},
    }
    for role, expected in expected_without_aios.items():
        actual = permissions_for_role(role) - {Permission.AIOS_INVOKE}
        assert actual == expected, f"{role.value} lost or gained an unrelated permission"


def test_an_unknown_role_may_not_invoke_orchestration() -> None:
    assert has_permission(None, Permission.AIOS_INVOKE) is False
    assert has_permission(resolve_trusted_role(_user("nobody")), Permission.AIOS_INVOKE) is False
