"""The permission catalog and the role-to-permission policy.

Closes Phase 0 audit BLOCKER-2: ``users.role`` was read in exactly one
place (``api/v1/auth.py``, echoed to the client) and never enforced, so
every authenticated organization member held effective Owner-level API
access. The five-tier model existed only in the browser
(``frontend/src/features/rbac/roles.ts``), whose own comment claims
"Server re-validates everything" -- it did not.

Scope of this slice (deliberately minimal). Management decision **M-4**
(the authoritative role model and per-action approval authorities) is
still open, and backlog risk R-1 warns against engineering inventing an
authority model. So this policy binds only what current repository
artefacts already state:

* the role *names* are exactly the five already defined in
  ``roles.ts`` -- no new vocabulary is introduced here;
* the *split* is the coarsest one that closes BLOCKER-2 -- ``viewer`` is
  read-only, every other recognized role may write, and organization
  management is admin-class (``navConfig.ts`` gates Settings/Users at
  ``Role.Admin``).

The finer ``editor`` / ``approver`` / ``admin`` distinction is
intentionally *not* encoded and remains deferred to M-4. Ratifying M-4
should be a single edit to ``ROLE_PERMISSIONS`` below.

Only permissions justified by routes that exist today are catalogued.
There is no ``user.manage`` permission because no user-management route
exists yet; adding one is a later slice's job.

Everything here is deterministic in-process code: no LLM, no model
provider, no network, no database, and no request-supplied value ever
reaches a decision.
"""

from enum import Enum
from types import MappingProxyType
from typing import Mapping

from app.domain.entities.user import User


class Permission(str, Enum):
    """Every capability a route may require. Unknown values are denied."""

    ORGANIZATION_MANAGE = "organization.manage"
    ENGAGEMENT_MANAGE = "engagement.manage"
    DOCUMENT_UPLOAD = "document.upload"
    DOCUMENT_PROCESS = "document.process"
    ANALYSIS_RUN = "analysis.run"
    EVIDENCE_REVIEW = "evidence.review"


class Role(str, Enum):
    """The five roles defined by the approved UI tier model (spec section 4).

    Mirrors ``frontend/src/features/rbac/roles.ts`` exactly. Membership in
    this enum is what makes a stored ``users.role`` value *recognized*;
    anything else is treated as unknown and denied.
    """

    VIEWER = "viewer"
    EDITOR = "editor"
    APPROVER = "approver"
    ADMIN = "admin"
    OWNER = "owner"


_WRITE_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.ENGAGEMENT_MANAGE,
        Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_PROCESS,
        Permission.ANALYSIS_RUN,
    }
)

_ADMIN_PERMISSIONS: frozenset[Permission] = _WRITE_PERMISSIONS | {
    Permission.ORGANIZATION_MANAGE
}

#: MVP Slice 4 (Evidence Review Lifecycle). Held as its own set, not
#: folded into ``_WRITE_PERMISSIONS``, precisely because *who may approve
#: evidence* is the question **M-4** exists to answer and backlog risk
#: R-1 forbade engineering from answering on its own.
#:
#: **M-4 is now recorded**, and it draws the approver/editor line that the
#: interim policy deliberately declined to invent: evidence review is an
#: *approval* authority, not a write authority. Producing content and
#: approving it as evidence are separate duties, so the role that uploads
#: and processes a document is not the role that may declare it verified
#: evidence -- that separation is the whole point of a review step, and an
#: editor who could approve their own upload would make the step
#: decorative.
#:
#: The recorded matrix is therefore: ``viewer`` denied, ``editor`` denied,
#: ``approver``/``admin``/``owner`` allowed, and a missing or unrecognized
#: role denied by ``permissions_for_role``'s deny-by-default lookup.
#:
#: This set is still held separately rather than merged into the
#: approver-class values, so the roles that hold evidence review remain
#: greppable from one place and a future re-widening stays a single edit.
_EVIDENCE_REVIEW_PERMISSIONS: frozenset[Permission] = frozenset(
    {Permission.EVIDENCE_REVIEW}
)

#: The single authoritative role -> permission policy. Read-only at runtime:
#: the mapping is a ``MappingProxyType`` and every value is a ``frozenset``,
#: so neither the policy nor any individual permission set can be mutated
#: by accident (or by a compromised code path) after import.
ROLE_PERMISSIONS: Mapping[Role, frozenset[Permission]] = MappingProxyType(
    {
        # Read-only. Holds no write permission at all -- this is the exact
        # bypass the audit recorded (a viewer calling POST /documents).
        Role.VIEWER: frozenset(),
        # Writes, but does not approve. M-4 separates producing evidence
        # from approving it, so the editor keeps every upload, processing,
        # analysis and engagement permission and holds no evidence-review
        # authority. This is the only role whose set M-4 changed.
        Role.EDITOR: _WRITE_PERMISSIONS,
        # The first role M-4 grants approval authority to: the same write
        # permissions as an editor, plus the authority to decide evidence.
        Role.APPROVER: _WRITE_PERMISSIONS | _EVIDENCE_REVIEW_PERMISSIONS,
        Role.ADMIN: _ADMIN_PERMISSIONS | _EVIDENCE_REVIEW_PERMISSIONS,
        Role.OWNER: _ADMIN_PERMISSIONS | _EVIDENCE_REVIEW_PERMISSIONS,
    }
)


def resolve_trusted_role(user: User) -> Role | None:
    """Resolve the server-stored role for ``user``, or ``None`` if unusable.

    The only input is the ``User`` profile loaded from the database by
    ``get_current_user``. Request bodies, query parameters and headers are
    never consulted. A missing role, a non-string role, or a value outside
    :class:`Role` all resolve to ``None``, which denies every permission.

    Surrounding whitespace and letter case are normalized because the
    ``users.role`` column is free-form ``varchar(50)`` with no database
    constraint; ``"Admin"`` is the same stored intent as ``"admin"``.
    """

    raw = user.role
    if not isinstance(raw, str):
        return None
    try:
        return Role(raw.strip().lower())
    except ValueError:
        return None


def permissions_for_role(role: Role | None) -> frozenset[Permission]:
    """Return the immutable permission set granted to ``role``.

    An unrecognized or missing role holds no permissions.
    """

    if role is None:
        return frozenset()
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: Role | None, permission: Permission | str) -> bool:
    """Decide whether ``role`` may exercise ``permission``. Deny by default.

    Fails closed on every uncertain input: a missing role, an unrecognized
    role, and a permission outside the catalog all return ``False``.
    """

    if role is None:
        return False
    try:
        required = Permission(permission)
    except ValueError:
        return False
    return required in permissions_for_role(role)
