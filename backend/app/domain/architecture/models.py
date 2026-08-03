"""Types describing the canonical GH Intelligence Hub architecture.

These are plain, framework-agnostic value objects in the same spirit as
``app.domain.entities``: no SQLAlchemy, no Pydantic, no ORM relationships.
Every type is frozen and slotted so the registry in ``registry.py`` and
``capability.py`` cannot be mutated by accident at runtime.

Two independent states are deliberately modelled, because conflating them is
how an interface ends up offering a control that leads nowhere:

- ``ActivationState`` is the *commercial* state published by the Founder
  Blueprint (Active / Incubating / Planned). It says what the business has
  decided to sell.
- ``BuildState`` is the *technical* state of this codebase (Reference /
  In Build / Production). It says what actually exists behind the interface.

An Active hub with a Reference build state is the normal, honest position
today. Only ``BuildState`` may unlock a functional control.
"""

from dataclasses import dataclass
from enum import Enum

from app.core.exceptions import ValidationError


class BuildState(str, Enum):
    """How much of a product domain actually exists in this codebase."""

    REFERENCE = "reference"
    IN_BUILD = "in_build"
    PRODUCTION = "production"


class ActivationState(str, Enum):
    """Commercial activation state published by the Founder Blueprint."""

    ACTIVE = "active"
    INCUBATING = "incubating"
    PLANNED = "planned"


class DomainAction(str, Enum):
    """Functional controls a product domain may offer to a user."""

    UPLOAD = "upload"
    QUERY = "query"
    ANALYSIS = "analysis"
    CALCULATION = "calculation"
    APPROVAL = "approval"


class UnknownIntelligenceHubError(ValidationError):
    """Raised for a hub code outside the canonical IH-00..IH-11 range."""


class ForbiddenIntelligenceHubError(UnknownIntelligenceHubError):
    """Raised for a retired or never-valid hub code.

    The retired twelfth-hub family listed in ``registry.FORBIDDEN_HUB_CODES``
    is the only such family today. This is a subclass of
    :class:`UnknownIntelligenceHubError` so a caller that only cares that a
    code is not canonical can catch the single base type.
    """


@dataclass(frozen=True, slots=True)
class ReportedBusinessLine:
    """One of the six lines the nineteen operating hubs consolidate into."""

    code: str
    name: str


@dataclass(frozen=True, slots=True)
class OperatingHub:
    """A delivery unit belonging to exactly one Intelligence Hub."""

    name: str
    activation_state: ActivationState


@dataclass(frozen=True, slots=True)
class IntelligenceHub:
    """A durable domain layer governing one or more operating hubs.

    ``reported_line`` is ``None`` only for IH-00, which is a governance layer
    and carries no reported revenue line.
    """

    code: str
    name: str
    reported_line: str | None
    operating_hubs: tuple[OperatingHub, ...]


@dataclass(frozen=True, slots=True)
class ProductDomain:
    """A product domain the platform interface may represent.

    ``offered_actions`` is a declaration, not a grant: ``capability`` refuses
    to surface any action for a domain that has no working backend.
    """

    key: str
    intelligence_hub: str
    build_state: BuildState
    activation_state: ActivationState
    offered_actions: frozenset[DomainAction] = frozenset()


@dataclass(frozen=True, slots=True)
class DomainCapability:
    """What shared product logic is allowed to present for one domain."""

    domain: str
    available: bool
    build_state: BuildState
    activation_state: ActivationState
    intelligence_hub: str | None
    offered_actions: frozenset[DomainAction]
    message: str

    def offers(self, action: DomainAction) -> bool:
        """Return whether this domain may present ``action`` to a user."""

        return action in self.offered_actions
