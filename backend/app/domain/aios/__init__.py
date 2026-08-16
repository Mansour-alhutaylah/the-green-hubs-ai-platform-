"""AIOS orchestration domain: contracts, registries and the client port.

n8n orchestrates. This application authenticates, authorizes, resolves
the tenant and controls every product action. Nothing in this package
reaches a database, a network or a model provider -- it is the policy
the AIOS layer is built from, and it is all deterministic.
"""

from app.domain.aios.client import (
    AIOSClient,
    AIOSClientError,
    AIOSDispatch,
    AIOSTimeoutError,
    AIOSUnavailableError,
    AIOSUnexpectedResponseError,
)
from app.domain.aios.contracts import (
    CONTRACT_VERSION,
    FORBIDDEN_ACTOR_FIELDS,
    GENERIC_VERIFICATION_FAILURE,
    TERMINAL_STATUSES,
    AIOSErrorCategory,
    AIOSStatus,
    find_forbidden_field,
    is_supported_contract_version,
    parse_status,
    safe_message_for,
)
from app.domain.aios.roles import (
    ACTIVE_ROLES,
    ROLE_ACTIVATION,
    AIOSRole,
    RoleActivation,
    is_role_active,
    resolve_role,
)
from app.domain.aios.tools import permitted_tools
from app.domain.aios.workflows import (
    ALLOWED_WORKFLOW_IDENTIFIERS,
    MAX_FOUNDATION_AUTONOMY_LEVEL,
    NORA_HEALTH_CHECK,
    WORKFLOW_REGISTRY,
    AutonomyLevel,
    RegisteredWorkflow,
    is_dispatchable,
    resolve_workflow,
)

__all__ = [
    "ACTIVE_ROLES",
    "AIOSClient",
    "AIOSClientError",
    "AIOSDispatch",
    "AIOSErrorCategory",
    "AIOSRole",
    "AIOSStatus",
    "AIOSTimeoutError",
    "AIOSUnavailableError",
    "AIOSUnexpectedResponseError",
    "ALLOWED_WORKFLOW_IDENTIFIERS",
    "AutonomyLevel",
    "CONTRACT_VERSION",
    "FORBIDDEN_ACTOR_FIELDS",
    "GENERIC_VERIFICATION_FAILURE",
    "MAX_FOUNDATION_AUTONOMY_LEVEL",
    "NORA_HEALTH_CHECK",
    "ROLE_ACTIVATION",
    "RegisteredWorkflow",
    "RoleActivation",
    "TERMINAL_STATUSES",
    "WORKFLOW_REGISTRY",
    "find_forbidden_field",
    "is_dispatchable",
    "is_role_active",
    "is_supported_contract_version",
    "parse_status",
    "permitted_tools",
    "resolve_role",
    "resolve_workflow",
    "safe_message_for",
]
