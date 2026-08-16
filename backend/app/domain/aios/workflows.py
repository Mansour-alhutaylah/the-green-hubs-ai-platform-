"""The workflow allowlist: what may be dispatched, at what autonomy.

Controlled application configuration, exactly like
``app.domain.architecture.registry``: no table, no migration, no runtime
write path. Nothing outside this module may define a dispatchable
workflow, and nothing at runtime may add one -- the registry is a
``MappingProxyType`` of frozen dataclasses, so a compromised code path
cannot widen it after import.

The foundation phase registers **one** workflow. The other names from
the operating model (Master Inbox, Daily Founder Brief, the shared error
handler) are deliberately *absent* rather than present-and-disabled: a
name that cannot be dispatched at all is a stronger guarantee than a
name guarded by a boolean, and Gate 1 authorized exactly one build.

Autonomy is recorded per workflow and capped for the phase. Founder
decision (Gate 1): begin at Levels 0-2. The Health Check is Level 0 --
it reads nothing, writes nothing, and calls nothing but the
application's own verification endpoint.
"""

from dataclasses import dataclass
from enum import Enum, IntEnum
from types import MappingProxyType
from typing import Final, Mapping

from app.domain.aios.roles import AIOSRole, is_role_active


class AutonomyLevel(IntEnum):
    """The five approved autonomy levels, preserved verbatim.

    ``IntEnum`` because the levels are genuinely ordered -- "no higher
    than Level 2" is a comparison, and encoding it as one keeps
    :data:`MAX_FOUNDATION_AUTONOMY_LEVEL` honest rather than a lookup
    table someone must remember to update.
    """

    READ_ONLY = 0
    INTERNAL_DRAFT = 1
    CONTROLLED_INTERNAL_WRITE = 2
    APPROVAL_GATED_EXTERNAL = 3
    PRE_AUTHORIZED_EXTERNAL = 4


class AIOSN8NWebhookMode(str, Enum):
    """The only two reviewed n8n webhook endpoint modes."""

    PRODUCTION = "production"
    TEST = "test"


#: Test webhooks are an editor-only staging/development mechanism. An
#: environment outside this explicit set is denied rather than guessed from
#: its name or from the configured n8n host.
TEST_WEBHOOK_ENVIRONMENTS: Final[frozenset[str]] = frozenset(
    {"development", "test", "testing", "local", "staging"}
)


#: Founder decision (Gate 1): begin at Levels 0-2. A registry entry above
#: this level is a policy violation, and the module refuses to define one
#: -- see the assertion at the foot of this file.
MAX_FOUNDATION_AUTONOMY_LEVEL: Final = AutonomyLevel.CONTROLLED_INTERNAL_WRITE


@dataclass(frozen=True, slots=True)
class RegisteredWorkflow:
    """One dispatchable workflow and everything dispatch needs to know."""

    #: The stable wire identifier, ``<role>.<purpose>``. Never renamed
    #: once dispatched -- it appears in signatures and execution records.
    identifier: str
    #: The operating function that owns it.
    role: AIOSRole
    #: Semantic version, echoed in response metadata.
    version: str
    #: What this workflow is permitted to do.
    autonomy_level: AutonomyLevel
    #: The published-workflow path appended in production mode.
    production_webhook_path: str
    #: The temporary listener path used only by n8n's Test Webhook mode.
    test_webhook_path: str


#: The one workflow Gate 1 approved for implementation.
NORA_HEALTH_CHECK: Final = "nora.health_check"
NORA_HEALTH_CHECK_PRODUCTION_WEBHOOK_PATH: Final = (
    "/webhook/gh-aios/v1/nora/health-check"
)
NORA_HEALTH_CHECK_TEST_WEBHOOK_PATH: Final = (
    "/webhook-test/gh-aios/v1/nora/health-check"
)

WORKFLOW_REGISTRY: Final[Mapping[str, RegisteredWorkflow]] = MappingProxyType(
    {
        NORA_HEALTH_CHECK: RegisteredWorkflow(
            identifier=NORA_HEALTH_CHECK,
            role=AIOSRole.NORA,
            version="1.0.0",
            autonomy_level=AutonomyLevel.READ_ONLY,
            production_webhook_path=NORA_HEALTH_CHECK_PRODUCTION_WEBHOOK_PATH,
            test_webhook_path=NORA_HEALTH_CHECK_TEST_WEBHOOK_PATH,
        )
    }
)

#: Every dispatchable identifier. Derived from the registry so the two
#: cannot disagree.
ALLOWED_WORKFLOW_IDENTIFIERS: Final[frozenset[str]] = frozenset(WORKFLOW_REGISTRY)


def resolve_workflow(raw: object) -> RegisteredWorkflow | None:
    """Return the registered workflow for ``raw``, or ``None``.

    Deny by default: an identifier outside the registry -- including a
    name reserved in the operating model but not yet approved, such as
    ``hafidh.master_inbox`` -- resolves to ``None`` and is refused before
    anything is signed or dispatched.

    No normalization beyond rejecting non-strings. Identifiers are fixed,
    lowercase constants that appear inside a signature's canonical
    string; silently accepting ``"NORA.Health_Check"`` would mean signing
    one spelling and registering another.
    """

    if not isinstance(raw, str):
        return None
    return WORKFLOW_REGISTRY.get(raw)


def is_dispatchable(workflow: RegisteredWorkflow) -> bool:
    """Whether ``workflow`` may be dispatched right now.

    Both conditions must hold: its owning role is active, and its
    autonomy level is within the phase cap. Registration alone is not
    permission.
    """

    return (
        is_role_active(workflow.role)
        and workflow.autonomy_level <= MAX_FOUNDATION_AUTONOMY_LEVEL
    )


def resolve_webhook_path(
    workflow: RegisteredWorkflow,
    *,
    mode: AIOSN8NWebhookMode,
    environment: str,
) -> str:
    """Return one reviewed path, denying unsafe Test-mode environments.

    The destination is never inferred from the n8n base URL and no caller
    value can supply a path or prefix. Unknown modes also fail closed even
    though :class:`Settings` rejects them before this boundary.
    """

    validate_webhook_mode_environment(mode=mode, environment=environment)
    if mode is AIOSN8NWebhookMode.PRODUCTION:
        return workflow.production_webhook_path
    return workflow.test_webhook_path


def validate_webhook_mode_environment(
    *, mode: AIOSN8NWebhookMode, environment: str
) -> None:
    """Refuse Test mode outside the explicit non-production allowlist."""

    if mode is AIOSN8NWebhookMode.PRODUCTION:
        return
    if (
        mode is AIOSN8NWebhookMode.TEST
        and environment.strip().lower() in TEST_WEBHOOK_ENVIRONMENTS
    ):
        return

    raise RuntimeError(
        "AIOS_N8N_WEBHOOK_MODE=test is allowed only in an explicitly "
        "approved non-production environment"
    )


# The registry is small and hand-written, so the phase cap is checked at
# import: a Level 3+ entry added by a future edit fails immediately and
# loudly rather than being discovered by a workflow that acts externally.
for _registered in WORKFLOW_REGISTRY.values():
    if _registered.autonomy_level > MAX_FOUNDATION_AUTONOMY_LEVEL:  # pragma: no cover
        raise RuntimeError(
            f"Workflow {_registered.identifier} declares autonomy level "
            f"{_registered.autonomy_level}, above the approved foundation "
            f"maximum {MAX_FOUNDATION_AUTONOMY_LEVEL}."
        )
    if not _registered.production_webhook_path.startswith("/webhook/"):
        raise RuntimeError("Production AIOS webhook paths must start with /webhook/")
    if not _registered.test_webhook_path.startswith("/webhook-test/"):
        raise RuntimeError("Test AIOS webhook paths must start with /webhook-test/")
    if _registered.production_webhook_path == _registered.test_webhook_path:
        raise RuntimeError("Production and Test AIOS webhook paths must be distinct")
