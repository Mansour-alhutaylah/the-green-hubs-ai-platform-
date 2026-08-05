"""Server-side authorization primitives.

Deliberately framework-independent (no FastAPI imports) so the permission
catalog and role policy stay testable in isolation and reusable by future
evidence, approval, audit and PMO capabilities. The FastAPI binding lives
in ``app.api.deps.require_permission``.
"""

from app.domain.security.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    Role,
    has_permission,
    permissions_for_role,
    resolve_trusted_role,
)

__all__ = [
    "ROLE_PERMISSIONS",
    "Permission",
    "Role",
    "has_permission",
    "permissions_for_role",
    "resolve_trusted_role",
]
