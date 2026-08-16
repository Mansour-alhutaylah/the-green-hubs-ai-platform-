"""The AIOS role registry and its activation states.

The nine names below are **operating functions, not autonomous
employees**. Each is a versioned prompt, a workflow role, a routing
policy, a tool permission set and its human checkpoints -- nothing here
claims that nine agents work independently.

Naming a role is not building one. This module keeps the two apart the
same way ``app.domain.architecture.capability`` keeps a *named* product
domain apart from a *built* one: the registry lists all nine, and
:func:`is_role_active` refuses eight of them. Founder decision (Gate 1)
records exactly one active orchestration role for the foundation phase:

* ``NORA`` -- active. The only role a workflow may currently route to.
* ``HAFIDH`` -- declared, inactive. Activates only when the Master Inbox
  workflow is approved for implementation, which it is not.
* the remaining seven -- declared, inactive.

Deny by default: an unrecognized name resolves to ``None`` and is
therefore never active.
"""

from enum import Enum
from types import MappingProxyType
from typing import Final, Mapping


class AIOSRole(str, Enum):
    """The nine operating functions named by the operating model."""

    NORA = "NORA"
    HAFIDH = "HAFIDH"
    RABT = "RABT"
    MIZAN = "MIZAN"
    RAQM = "RAQM"
    ATHAR = "ATHAR"
    BASIRAH = "BASIRAH"
    SANAD = "SANAD"
    TAWAZUN = "TAWAZUN"


class RoleActivation(str, Enum):
    """Whether a declared role may currently be routed to."""

    #: Routable now.
    ACTIVE = "active"
    #: Named in the registry so the structure is coherent, and refused at
    #: runtime. This is the state that makes "reserved" mean something.
    DECLARED_INACTIVE = "declared_inactive"


#: The authoritative activation policy. Read-only at runtime
#: (``MappingProxyType``), so no code path can activate a role after
#: import -- activation is a reviewed edit to this table, which is
#: exactly the visibility a Founder decision deserves.
ROLE_ACTIVATION: Final[Mapping[AIOSRole, RoleActivation]] = MappingProxyType(
    {
        AIOSRole.NORA: RoleActivation.ACTIVE,
        # Gate 1: activates only when Master Inbox is approved. It is not.
        AIOSRole.HAFIDH: RoleActivation.DECLARED_INACTIVE,
        AIOSRole.RABT: RoleActivation.DECLARED_INACTIVE,
        AIOSRole.MIZAN: RoleActivation.DECLARED_INACTIVE,
        AIOSRole.RAQM: RoleActivation.DECLARED_INACTIVE,
        AIOSRole.ATHAR: RoleActivation.DECLARED_INACTIVE,
        AIOSRole.BASIRAH: RoleActivation.DECLARED_INACTIVE,
        AIOSRole.SANAD: RoleActivation.DECLARED_INACTIVE,
        AIOSRole.TAWAZUN: RoleActivation.DECLARED_INACTIVE,
    }
)

#: Every role currently routable. Derived, never hand-maintained, so it
#: cannot drift from the table above.
ACTIVE_ROLES: Final[frozenset[AIOSRole]] = frozenset(
    role for role, state in ROLE_ACTIVATION.items() if state is RoleActivation.ACTIVE
)


def resolve_role(raw: object) -> AIOSRole | None:
    """Resolve a role name, or ``None`` if it is not one of the nine."""

    if not isinstance(raw, str):
        return None
    try:
        return AIOSRole(raw.strip().upper())
    except ValueError:
        return None


def is_role_active(role: AIOSRole | str | None) -> bool:
    """Whether ``role`` may currently be routed to. Deny by default."""

    resolved = role if isinstance(role, AIOSRole) else resolve_role(role)
    if resolved is None:
        return False
    return ROLE_ACTIVATION[resolved] is RoleActivation.ACTIVE
