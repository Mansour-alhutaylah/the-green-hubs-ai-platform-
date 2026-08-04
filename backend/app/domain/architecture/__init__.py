"""Canonical GH architecture register and product-domain capability guard.

One source of truth for the twelve Intelligence Hubs, the nineteen operating
hubs, the six reported business lines, and what each product domain is
actually allowed to present today.
"""

from app.domain.architecture.capability import (
    APPROVED_MVP_DOMAINS,
    AVAILABLE_MESSAGE,
    NOT_BUILT_MESSAGE,
    PRODUCT_DOMAINS,
    build_capability,
    domain_offers,
    get_domain_capability,
    is_approved_mvp_domain,
    normalize_domain_key,
)
from app.domain.architecture.models import (
    ActivationState,
    BuildState,
    DomainAction,
    DomainCapability,
    ForbiddenIntelligenceHubError,
    IntelligenceHub,
    OperatingHub,
    ProductDomain,
    ReportedBusinessLine,
    UnknownIntelligenceHubError,
)
from app.domain.architecture.registry import (
    CANONICAL_HUB_CODES,
    FORBIDDEN_HUB_CODES,
    INTELLIGENCE_HUB_COUNT,
    INTELLIGENCE_HUBS,
    OPERATING_HUB_COUNT,
    REPORTED_BUSINESS_LINE_COUNT,
    REPORTED_BUSINESS_LINES,
    RETIRED_HUB_ORDINAL,
    assert_canonical_hub,
    get_intelligence_hub,
    get_reported_business_line,
    is_canonical_hub,
    iter_operating_hubs,
)

__all__ = [
    "APPROVED_MVP_DOMAINS",
    "AVAILABLE_MESSAGE",
    "CANONICAL_HUB_CODES",
    "FORBIDDEN_HUB_CODES",
    "INTELLIGENCE_HUBS",
    "INTELLIGENCE_HUB_COUNT",
    "NOT_BUILT_MESSAGE",
    "OPERATING_HUB_COUNT",
    "PRODUCT_DOMAINS",
    "REPORTED_BUSINESS_LINES",
    "REPORTED_BUSINESS_LINE_COUNT",
    "RETIRED_HUB_ORDINAL",
    "ActivationState",
    "BuildState",
    "DomainAction",
    "DomainCapability",
    "ForbiddenIntelligenceHubError",
    "IntelligenceHub",
    "OperatingHub",
    "ProductDomain",
    "ReportedBusinessLine",
    "UnknownIntelligenceHubError",
    "assert_canonical_hub",
    "build_capability",
    "domain_offers",
    "get_domain_capability",
    "get_intelligence_hub",
    "get_reported_business_line",
    "is_approved_mvp_domain",
    "is_canonical_hub",
    "iter_operating_hubs",
    "normalize_domain_key",
]
