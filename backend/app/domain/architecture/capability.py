"""What shared product logic may present for a given product domain.

The four approved MVP domains -- ESG, Carbon, Energy and PMO -- are named in
the canonical architecture, but naming a domain is not the same as building
one. Each entry below carries its own ``BuildState``, assigned from evidence
in this repository rather than from the Blueprint's commercial ambition.

Today no domain-specific backend exists: there is no ESG, Carbon, Energy or
PMO route, service, table or calculation in ``backend/app``, and the only
domain page in the interface (Carbon) is an explicit "coming soon"
placeholder. All four are therefore ``BuildState.REFERENCE``.

``get_domain_capability`` is the single gate. A domain that is not built
returns ``available=False`` with an empty action set, so shared product logic
physically cannot offer an upload, query, analysis, calculation or approval
control that leads to a backend which does not exist -- even if someone later
declares actions on a Reference domain by mistake.
"""

from types import MappingProxyType
from typing import Final, Mapping

from app.domain.architecture.models import (
    ActivationState,
    BuildState,
    DomainAction,
    DomainCapability,
    ProductDomain,
)

_AVAILABLE_BUILD_STATES: Final[frozenset[BuildState]] = frozenset(
    (BuildState.IN_BUILD, BuildState.PRODUCTION)
)

NOT_BUILT_MESSAGE: Final = (
    "This domain is defined in the canonical architecture and is not yet "
    "built. No upload, query, analysis, calculation, or approval control is "
    "offered."
)
AVAILABLE_MESSAGE: Final = (
    "This domain has backend capability. Offered controls are listed in "
    "offered_actions."
)

PRODUCT_DOMAINS: Final[Mapping[str, ProductDomain]] = MappingProxyType(
    {
        domain.key: domain
        for domain in (
            ProductDomain(
                key="esg",
                intelligence_hub="IH-02",
                build_state=BuildState.REFERENCE,
                activation_state=ActivationState.ACTIVE,
            ),
            ProductDomain(
                key="carbon",
                intelligence_hub="IH-03",
                build_state=BuildState.REFERENCE,
                activation_state=ActivationState.ACTIVE,
            ),
            ProductDomain(
                key="energy",
                intelligence_hub="IH-04",
                build_state=BuildState.REFERENCE,
                activation_state=ActivationState.ACTIVE,
            ),
            ProductDomain(
                key="pmo",
                intelligence_hub="IH-07",
                build_state=BuildState.REFERENCE,
                activation_state=ActivationState.ACTIVE,
            ),
        )
    }
)

APPROVED_MVP_DOMAINS: Final[frozenset[str]] = frozenset(PRODUCT_DOMAINS)


def normalize_domain_key(domain: str) -> str:
    """Return the lookup key for a caller-supplied domain name."""

    return domain.strip().lower()


def is_approved_mvp_domain(domain: str) -> bool:
    """Return whether ``domain`` is one of the four approved MVP domains."""

    return normalize_domain_key(domain) in APPROVED_MVP_DOMAINS


def build_capability(product_domain: ProductDomain) -> DomainCapability:
    """Derive what may be presented for one registered product domain.

    Only ``BuildState`` unlocks a control. Declared actions on a domain that
    is not built are dropped here rather than trusted, so a mistaken
    declaration cannot reach the interface.
    """

    available = product_domain.build_state in _AVAILABLE_BUILD_STATES
    return DomainCapability(
        domain=product_domain.key,
        available=available,
        build_state=product_domain.build_state,
        activation_state=product_domain.activation_state,
        intelligence_hub=product_domain.intelligence_hub,
        offered_actions=product_domain.offered_actions if available else frozenset(),
        message=AVAILABLE_MESSAGE if available else NOT_BUILT_MESSAGE,
    )


def get_domain_capability(domain: str) -> DomainCapability:
    """Return what may be presented for ``domain``.

    An unregistered domain is treated exactly like an unbuilt one: refusing by
    default is the only safe answer for a name this registry does not know.
    """

    key = normalize_domain_key(domain)
    product_domain = PRODUCT_DOMAINS.get(key)

    if product_domain is None:
        return DomainCapability(
            domain=key,
            available=False,
            build_state=BuildState.REFERENCE,
            activation_state=ActivationState.PLANNED,
            intelligence_hub=None,
            offered_actions=frozenset(),
            message=NOT_BUILT_MESSAGE,
        )

    return build_capability(product_domain)


def domain_offers(domain: str, action: DomainAction) -> bool:
    """Return whether ``domain`` may present ``action`` to a user."""

    return get_domain_capability(domain).offers(action)
