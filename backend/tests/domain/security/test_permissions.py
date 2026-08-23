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
_RBAC_DIR = (
    Path(__file__).resolve().parents[3].parent / "frontend" / "src" / "features" / "rbac"
)
_ROLES_TS = _RBAC_DIR / "roles.ts"
_PERMISSIONS_TS = _RBAC_DIR / "permissions.ts"


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


def test_the_frontend_evidence_review_policy_matches_the_backend() -> None:
    """The frontend decides which review controls are *offered*; this
    module decides which commands are *allowed*. They are separate
    concerns, but a disagreement between them is always a defect: either
    a reviewer is shown a control the server will refuse, or an
    authorized reviewer is silently denied the control they are entitled
    to use.

    The backend remains the enforcement boundary regardless -- this pins
    the UX mirror to the policy, it does not delegate authority to it."""

    source = _PERMISSIONS_TS.read_text(encoding="utf-8")
    block = source.split("EVIDENCE_REVIEW_ROLES: readonly Role[] = [", 1)[1].split("]", 1)[0]
    # `Role.Approver` -> `approver`, matching the backend's enum values.
    frontend_roles = {name.lower() for name in re.findall(r"Role\.([A-Za-z]+)", block)}
    backend_roles = {
        role.value for role in Role if Permission.EVIDENCE_REVIEW in permissions_for_role(role)
    }

    assert frontend_roles == backend_roles


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


#: The recorded **M-4** evidence-review matrix, written out once, in full,
#: as the decision itself states it. Every M-4 assertion below reads from
#: this table rather than restating a role list, so the recorded policy and
#: the tests that pin it cannot drift apart.
M4_EVIDENCE_REVIEW_MATRIX: dict[Role, bool] = {
    Role.VIEWER: False,
    Role.EDITOR: False,
    Role.APPROVER: True,
    Role.ADMIN: True,
    Role.OWNER: True,
}


def test_the_m4_matrix_covers_every_role() -> None:
    """A role added later must be given an explicit M-4 answer rather
    than silently escaping the matrix below."""

    assert set(M4_EVIDENCE_REVIEW_MATRIX) == set(Role)


@pytest.mark.parametrize(("role", "allowed"), sorted(M4_EVIDENCE_REVIEW_MATRIX.items()))
def test_evidence_review_follows_the_recorded_m4_matrix(role: Role, allowed: bool) -> None:
    """The authoritative pin for the evidence-review authorization policy.

    This assertion -- not any API test -- is where the evidence-review
    role mapping is decided; ``test_document_evidence.py`` derives its
    allowed/denied parametrization from ``ROLE_PERMISSIONS`` so that the
    tests follow the policy rather than establish it.

    **M-4 is recorded**: evidence review is an approval authority, not a
    write authority. ``approver``, ``admin`` and ``owner`` hold it;
    ``viewer`` and ``editor`` do not. The editor exclusion is the
    substance of the decision -- the role that uploads and processes a
    document is deliberately not the role that may approve it as
    evidence, because a reviewer approving their own upload makes the
    review step decorative."""

    assert has_permission(role, Permission.EVIDENCE_REVIEW) is allowed
    assert (Permission.EVIDENCE_REVIEW in permissions_for_role(role)) is allowed


def test_evidence_review_is_granted_to_exactly_the_documented_roles() -> None:
    """The same policy stated as a set, so a role gaining the permission
    without a matrix entry fails here even if the parametrization above
    were somehow narrowed."""

    granted = {role for role in Role if Permission.EVIDENCE_REVIEW in permissions_for_role(role)}

    assert granted == {Role.APPROVER, Role.ADMIN, Role.OWNER}
    assert Role.VIEWER not in granted
    assert Role.EDITOR not in granted


def test_m4_removed_only_evidence_review_from_the_editor() -> None:
    """M-4 narrowed exactly one permission. An editor must keep every
    unrelated authority -- upload, processing, analysis and engagement
    management -- so this change cannot be mistaken for a general
    demotion of the role."""

    editor = permissions_for_role(Role.EDITOR)

    assert Permission.EVIDENCE_REVIEW not in editor
    assert editor == {
        Permission.ENGAGEMENT_MANAGE,
        Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_PROCESS,
        Permission.ANALYSIS_RUN,
    }


def test_an_approver_differs_from_an_editor_by_exactly_evidence_review() -> None:
    """The approver/editor split M-4 draws is this one permission and
    nothing else -- an approver gains no administrative authority."""

    difference = permissions_for_role(Role.APPROVER) ^ permissions_for_role(Role.EDITOR)

    assert difference == {Permission.EVIDENCE_REVIEW}


@pytest.mark.parametrize("raw_role", ["", "   ", "reviewer", "superuser", "EDITOR_", "None"])
def test_an_unknown_role_string_is_denied_evidence_review(raw_role: str) -> None:
    """Fail closed: a role value outside the catalog resolves to no role
    and therefore to no evidence-review authority."""

    resolved = resolve_trusted_role(_user(raw_role))

    assert has_permission(resolved, Permission.EVIDENCE_REVIEW) is False


def test_a_missing_role_is_denied_evidence_review() -> None:
    """A user row with no role at all is denied, not defaulted upward."""

    assert resolve_trusted_role(_user(None)) is None
    assert has_permission(None, Permission.EVIDENCE_REVIEW) is False


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
