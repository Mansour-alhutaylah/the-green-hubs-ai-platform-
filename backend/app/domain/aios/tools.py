"""What tools each operating role may use. Currently: none.

This module exists precisely *because* it is empty. A tool grant that has
nowhere to be declared gets made ad hoc at the point of use -- inside a
workflow node, invisible to review. Having the registry now means the
first Drive, email or messaging grant is a reviewed edit to a named
table, and the foundation phase's answer is one line rather than an
absence someone has to notice.

Founder decision (Gate 1): no Drive credential, no OpenAI/OpenRouter
credential, no messaging credential and no external action in the
foundation phase. The NORA Health Check needs no tool at all -- its only
outbound call is the orchestrator's own verification callback into this
application, which is protocol, not a tool.

Deny by default, twice over: an unknown role gets the empty set, and a
known role gets the empty set too.
"""

from types import MappingProxyType
from typing import Final, Mapping

from app.domain.aios.roles import AIOSRole
from app.domain.aios.workflows import AutonomyLevel

#: Every tool grant in the system, keyed by role. Every value is
#: deliberately empty for the foundation phase.
ROLE_TOOLS: Final[Mapping[AIOSRole, frozenset[str]]] = MappingProxyType(
    {role: frozenset() for role in AIOSRole}
)

#: The autonomy level at which a tool stops being an internal convenience
#: and becomes an external action requiring a recorded approval. Nothing
#: may be granted at or above this level in the foundation phase.
EXTERNAL_ACTION_LEVEL: Final = AutonomyLevel.APPROVAL_GATED_EXTERNAL


def permitted_tools(role: AIOSRole | None) -> frozenset[str]:
    """The tools ``role`` may use. Empty for every role, today."""

    if role is None:
        return frozenset()
    return ROLE_TOOLS.get(role, frozenset())


def may_use_tool(role: AIOSRole | None, tool: str) -> bool:
    """Whether ``role`` may use ``tool``. Always ``False`` today."""

    return tool in permitted_tools(role)
