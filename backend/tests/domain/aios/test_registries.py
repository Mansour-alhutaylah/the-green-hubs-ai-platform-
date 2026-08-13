"""The AIOS contract vocabulary and the three registries.

Everything here is deterministic in-process policy. The properties being
asserted are the ones that keep n8n from acquiring authority it was never
granted: deny by default, immutable at runtime, and *named* is not
*active*.
"""

import pytest

from app.domain.aios.contracts import (
    CONTRACT_VERSION,
    FORBIDDEN_ACTOR_FIELDS,
    GENERIC_VERIFICATION_FAILURE,
    INDISTINGUISHABLE_VERIFICATION_CATEGORIES,
    SAFE_ERROR_MESSAGES,
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
from app.domain.aios.tools import ROLE_TOOLS, may_use_tool, permitted_tools
from app.domain.aios.workflows import (
    ALLOWED_WORKFLOW_IDENTIFIERS,
    MAX_FOUNDATION_AUTONOMY_LEVEL,
    NORA_HEALTH_CHECK,
    WORKFLOW_REGISTRY,
    AutonomyLevel,
    is_dispatchable,
    resolve_workflow,
)

# ---------------------------------------------------------------------------
# Contract vocabulary
# ---------------------------------------------------------------------------


def test_the_contract_version_is_pinned() -> None:
    assert CONTRACT_VERSION == "1.0"
    assert is_supported_contract_version("1.0")


@pytest.mark.parametrize("raw", ["1", "1.1", "2.0", "", None, 1.0, {"v": "1.0"}])
def test_any_other_contract_version_is_refused(raw: object) -> None:
    """Rejected, never coerced. A version field tolerated when it
    disagrees is decoration."""

    assert not is_supported_contract_version(raw)


def test_every_status_has_a_stable_wire_value() -> None:
    assert {status.value for status in AIOSStatus} == {
        "accepted",
        "running",
        "completed",
        "rejected",
        "human_approval_required",
        "failed",
    }


def test_a_pause_is_not_a_terminal_outcome() -> None:
    """``human_approval_required`` is neither an approval nor a denial."""

    assert AIOSStatus.HUMAN_APPROVAL_REQUIRED not in TERMINAL_STATUSES
    assert TERMINAL_STATUSES == {
        AIOSStatus.COMPLETED,
        AIOSStatus.REJECTED,
        AIOSStatus.FAILED,
    }


@pytest.mark.parametrize(
    "raw", ["done", "ok", "success", "COMPLETED", "", None, 1, {"status": "completed"}]
)
def test_an_unrecognized_status_fails_closed(raw: object) -> None:
    """Never optimistically read as a success."""

    assert parse_status(raw) is None


def test_a_recognized_status_parses() -> None:
    assert parse_status("completed") is AIOSStatus.COMPLETED


def test_every_error_category_has_a_safe_message() -> None:
    for category in AIOSErrorCategory:
        assert safe_message_for(category)
    assert set(SAFE_ERROR_MESSAGES) == set(AIOSErrorCategory)


def test_no_safe_message_leaks_an_internal_detail() -> None:
    """A caller learns what went wrong, never how the system is built."""

    banned = (
        "secret",
        "key_id",
        "hmac",
        "sha256",
        "signature",
        "traceback",
        "sql",
        "postgres",
        "supabase",
        "n8n",
        "webhook",
        "openai",
        "http://",
        "https://",
    )
    for category, message in SAFE_ERROR_MESSAGES.items():
        lowered = message.lower()
        for term in banned:
            assert term not in lowered, f"{category.value} message leaks {term!r}"


def test_the_three_verification_failures_are_answered_identically() -> None:
    """Otherwise the endpoint is an oracle for which key ids exist."""

    assert INDISTINGUISHABLE_VERIFICATION_CATEGORIES == {
        AIOSErrorCategory.SIGNATURE_INVALID,
        AIOSErrorCategory.TIMESTAMP_OUT_OF_WINDOW,
        AIOSErrorCategory.UNSUPPORTED_KEY_ID,
    }
    assert GENERIC_VERIFICATION_FAILURE in INDISTINGUISHABLE_VERIFICATION_CATEGORIES
    messages = {
        SAFE_ERROR_MESSAGES[category]
        for category in INDISTINGUISHABLE_VERIFICATION_CATEGORIES
    }
    assert len(messages) == 1, "all three must produce one identical message"


# ---------------------------------------------------------------------------
# Forbidden authority fields
# ---------------------------------------------------------------------------


def test_the_forbidden_field_set_is_the_approved_one() -> None:
    assert FORBIDDEN_ACTOR_FIELDS == {
        "user_id",
        "organization_id",
        "role",
        "permission",
        "permissions",
        "reviewed_by",
        "evidence_status",
        "approval_state",
        "is_admin",
    }


@pytest.mark.parametrize("field", sorted(FORBIDDEN_ACTOR_FIELDS))
def test_a_forbidden_field_is_found_at_the_top_level(field: str) -> None:
    assert find_forbidden_field({field: "anything"}) == field


@pytest.mark.parametrize("field", sorted(FORBIDDEN_ACTOR_FIELDS))
def test_a_forbidden_field_is_found_when_nested(field: str) -> None:
    """A client blocked at the top level tries ``input.actor.<field>`` next."""

    payload = {"input": {"actor": {"deeply": {"nested": {field: "x"}}}}}
    assert find_forbidden_field(payload) == field


@pytest.mark.parametrize("field", sorted(FORBIDDEN_ACTOR_FIELDS))
def test_a_forbidden_field_is_found_inside_a_list(field: str) -> None:
    assert find_forbidden_field({"input": [{"a": 1}, {field: "x"}]}) == field


def test_case_and_whitespace_variants_are_caught() -> None:
    assert find_forbidden_field({"  Organization_ID  ": "x"}) == "organization_id"
    assert find_forbidden_field({"IS_ADMIN": True}) == "is_admin"


def test_an_ordinary_payload_is_left_alone() -> None:
    assert find_forbidden_field({}) is None
    assert find_forbidden_field({"input": {}}) is None
    assert find_forbidden_field({"input": {"note": "a report about a role"}}) is None
    # A *value* that reads like a forbidden name is ordinary data.
    assert find_forbidden_field({"input": {"label": "role"}}) is None
    assert find_forbidden_field(["role", "is_admin"]) is None


# ---------------------------------------------------------------------------
# Workflow registry
# ---------------------------------------------------------------------------


def test_exactly_one_workflow_is_registered() -> None:
    """Gate 1 authorized one build. Reserved names are absent, not
    present-and-disabled -- a name that cannot be dispatched at all is a
    stronger guarantee than one guarded by a boolean."""

    assert ALLOWED_WORKFLOW_IDENTIFIERS == {NORA_HEALTH_CHECK}


@pytest.mark.parametrize(
    "identifier",
    [
        "hafidh.master_inbox",
        "nora.router",
        "nora.daily_founder_brief",
        "shared.error_handler",
        "shared.human_checkpoint",
        "nora.health_check ",
        "NORA.HEALTH_CHECK",
        "Nora.Health_Check",
        "",
        None,
        123,
    ],
)
def test_anything_else_is_refused(identifier: object) -> None:
    """Including the reserved-but-unapproved names, and including
    case variants -- the identifier appears verbatim inside a signature's
    canonical string, so accepting a second spelling would mean signing
    one and registering another."""

    assert resolve_workflow(identifier) is None


def test_the_health_check_is_registered_correctly() -> None:
    workflow = resolve_workflow(NORA_HEALTH_CHECK)
    assert workflow is not None
    assert workflow.identifier == "nora.health_check"
    assert workflow.role is AIOSRole.NORA
    assert workflow.version == "1.0.0"
    assert workflow.autonomy_level is AutonomyLevel.READ_ONLY
    assert workflow.webhook_path.startswith("/webhook/gh-aios/v1/")


def test_the_health_check_is_dispatchable() -> None:
    workflow = resolve_workflow(NORA_HEALTH_CHECK)
    assert workflow is not None
    assert is_dispatchable(workflow)


def test_the_foundation_autonomy_cap_is_level_two() -> None:
    assert MAX_FOUNDATION_AUTONOMY_LEVEL is AutonomyLevel.CONTROLLED_INTERNAL_WRITE


def test_no_registered_workflow_exceeds_the_cap() -> None:
    for workflow in WORKFLOW_REGISTRY.values():
        assert workflow.autonomy_level <= MAX_FOUNDATION_AUTONOMY_LEVEL


def test_the_registry_cannot_be_mutated_at_runtime() -> None:
    with pytest.raises(TypeError):
        WORKFLOW_REGISTRY["hafidh.master_inbox"] = None  # type: ignore[index]


def test_a_registered_workflow_is_frozen() -> None:
    workflow = resolve_workflow(NORA_HEALTH_CHECK)
    assert workflow is not None
    with pytest.raises(Exception):
        workflow.autonomy_level = AutonomyLevel.PRE_AUTHORIZED_EXTERNAL  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Role registry: named is not active
# ---------------------------------------------------------------------------


def test_all_nine_roles_are_named() -> None:
    assert {role.value for role in AIOSRole} == {
        "NORA",
        "HAFIDH",
        "RABT",
        "MIZAN",
        "RAQM",
        "ATHAR",
        "BASIRAH",
        "SANAD",
        "TAWAZUN",
    }


def test_only_nora_is_active() -> None:
    """Gate 1: NORA is the only active orchestration role."""

    assert ACTIVE_ROLES == {AIOSRole.NORA}
    assert is_role_active(AIOSRole.NORA)


def test_hafidh_is_declared_but_inactive() -> None:
    """It activates only when Master Inbox is approved. It is not."""

    assert ROLE_ACTIVATION[AIOSRole.HAFIDH] is RoleActivation.DECLARED_INACTIVE
    assert not is_role_active(AIOSRole.HAFIDH)


@pytest.mark.parametrize(
    "role",
    [
        AIOSRole.HAFIDH,
        AIOSRole.RABT,
        AIOSRole.MIZAN,
        AIOSRole.RAQM,
        AIOSRole.ATHAR,
        AIOSRole.BASIRAH,
        AIOSRole.SANAD,
        AIOSRole.TAWAZUN,
    ],
)
def test_every_other_role_is_inactive(role: AIOSRole) -> None:
    assert not is_role_active(role)


@pytest.mark.parametrize("raw", ["", None, "nobody", "nora.health_check", 42])
def test_an_unknown_role_is_never_active(raw: object) -> None:
    assert resolve_role(raw) is None
    assert not is_role_active(raw)  # type: ignore[arg-type]


@pytest.mark.parametrize("raw", ["NORA", "nora", " Nora ", "nOrA"])
def test_a_role_name_is_normalized_but_a_workflow_identifier_is_not(raw: str) -> None:
    """The two registries normalize differently, on purpose.

    A role name is an operator-facing label and is normalized exactly as
    ``resolve_trusted_role`` normalizes a stored ``users.role`` -- case
    and surrounding whitespace are formatting, not intent.

    A workflow identifier is not: it appears *verbatim* inside a
    signature's canonical string, so accepting a second spelling would
    mean signing one string and re-deriving another. Asserting both here
    keeps the asymmetry deliberate rather than looking like an oversight.
    """

    assert resolve_role(raw) is AIOSRole.NORA
    assert is_role_active(raw)
    assert resolve_workflow(NORA_HEALTH_CHECK.upper()) is None
    assert resolve_workflow(f" {NORA_HEALTH_CHECK} ") is None


def test_role_activation_cannot_be_mutated_at_runtime() -> None:
    with pytest.raises(TypeError):
        ROLE_ACTIVATION[AIOSRole.HAFIDH] = RoleActivation.ACTIVE  # type: ignore[index]


# ---------------------------------------------------------------------------
# Tool registry: empty, for every role
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", list(AIOSRole))
def test_no_role_holds_any_tool(role: AIOSRole) -> None:
    """Founder decision (Gate 1): no Drive, provider or messaging tool in
    the foundation phase."""

    assert permitted_tools(role) == frozenset()


@pytest.mark.parametrize(
    "tool",
    [
        "google_drive.read",
        "google_drive.move",
        "openai.complete",
        "email.send",
        "telegram.send",
        "postgres.query",
        "supabase.service_role",
        "evidence.verify",
    ],
)
def test_no_role_may_use_any_named_tool(tool: str) -> None:
    for role in AIOSRole:
        assert not may_use_tool(role, tool)


def test_an_unknown_role_gets_the_empty_set() -> None:
    assert permitted_tools(None) == frozenset()


def test_the_tool_registry_cannot_be_mutated_at_runtime() -> None:
    with pytest.raises(TypeError):
        ROLE_TOOLS[AIOSRole.NORA] = frozenset({"google_drive.read"})  # type: ignore[index]
