"""The canonical architecture register.

Source of truth: Founder Blueprint MASTER v3.0.17 -- twelve Intelligence Hubs
(IH-00 to IH-11) governing nineteen operating hubs, consolidated into six
reported business lines. There is no twelfth Intelligence Hub.

This module is controlled application configuration, not persisted data: no
table, no migration, no runtime write path. Nothing else in the codebase may
define a hub code, an operating hub, or a reported line.

Convention: active product source must never spell the retired hub code out,
not even in prose. Refer to it as the retired hub ordinal and let
``FORBIDDEN_HUB_CODES`` derive the strings. Tests are free to use the literal.
"""

from types import MappingProxyType
from typing import Final, Mapping

from app.domain.architecture.models import (
    ActivationState,
    ForbiddenIntelligenceHubError,
    IntelligenceHub,
    OperatingHub,
    ReportedBusinessLine,
    UnknownIntelligenceHubError,
)

_ACTIVE = ActivationState.ACTIVE
_INCUBATING = ActivationState.INCUBATING
_PLANNED = ActivationState.PLANNED

REPORTED_BUSINESS_LINES: Final[Mapping[str, ReportedBusinessLine]] = MappingProxyType(
    {
        line.code: line
        for line in (
            ReportedBusinessLine("BU-01", "PMO & Execution"),
            ReportedBusinessLine("BU-02", "Energy, Carbon & Climate"),
            ReportedBusinessLine("BU-03", "Water"),
            ReportedBusinessLine("BU-04", "Social Impact & Local Content"),
            ReportedBusinessLine("BU-05", "AI & Platform"),
            ReportedBusinessLine("BU-06", "Advisory & Transformation"),
        )
    }
)

INTELLIGENCE_HUBS: Final[tuple[IntelligenceHub, ...]] = (
    IntelligenceHub(
        code="IH-00",
        name="Zero Intelligence Hub",
        reported_line=None,
        operating_hubs=(OperatingHub("Green Zero Hub", _ACTIVE),),
    ),
    IntelligenceHub(
        code="IH-01",
        name="Consulting & Transformation",
        reported_line="BU-06",
        operating_hubs=(
            OperatingHub("Green Consulting Hub", _ACTIVE),
            OperatingHub("Green Digital Transformation Hub", _INCUBATING),
        ),
    ),
    IntelligenceHub(
        code="IH-02",
        name="ESG Intelligence",
        reported_line="BU-06",
        operating_hubs=(OperatingHub("Green ESG Hub", _ACTIVE),),
    ),
    IntelligenceHub(
        code="IH-03",
        name="Carbon Intelligence",
        reported_line="BU-02",
        operating_hubs=(OperatingHub("Green Carbon Hub", _ACTIVE),),
    ),
    IntelligenceHub(
        code="IH-04",
        name="Energy Intelligence",
        reported_line="BU-02",
        operating_hubs=(OperatingHub("Green Energy Hub", _ACTIVE),),
    ),
    IntelligenceHub(
        code="IH-05",
        name="Water Intelligence",
        reported_line="BU-03",
        operating_hubs=(
            OperatingHub("Green Water Hub", _INCUBATING),
            OperatingHub("Green Water Delivery Hub", _PLANNED),
        ),
    ),
    IntelligenceHub(
        code="IH-06",
        name="Asset & Field Intelligence",
        reported_line="BU-01",
        operating_hubs=(
            OperatingHub("Green Technology Hub", _ACTIVE),
            OperatingHub("Green Materials Hub", _PLANNED),
        ),
    ),
    IntelligenceHub(
        code="IH-07",
        name="PMO Intelligence",
        reported_line="BU-01",
        operating_hubs=(
            OperatingHub("PMO Hub", _ACTIVE),
            OperatingHub("Green Project Management Hub", _INCUBATING),
        ),
    ),
    IntelligenceHub(
        code="IH-08",
        name="AI Intelligence",
        reported_line="BU-05",
        operating_hubs=(OperatingHub("Green AI Hub", _ACTIVE),),
    ),
    IntelligenceHub(
        code="IH-09",
        name="Knowledge & Innovation",
        reported_line="BU-05",
        operating_hubs=(
            OperatingHub("R&D Hub", _PLANNED),
            OperatingHub("Center of Knowledge Hub", _INCUBATING),
            OperatingHub("Green Training Hub", _INCUBATING),
        ),
    ),
    IntelligenceHub(
        code="IH-10",
        name="Finance Intelligence",
        reported_line="BU-06",
        operating_hubs=(OperatingHub("Green Finance Hub", _INCUBATING),),
    ),
    IntelligenceHub(
        code="IH-11",
        name="Social Impact Intelligence",
        reported_line="BU-04",
        operating_hubs=(
            OperatingHub("Green Social Impact Hub", _INCUBATING),
            OperatingHub("Green Nonprofit Transformation Hub", _INCUBATING),
        ),
    ),
)

INTELLIGENCE_HUB_COUNT: Final = 12
OPERATING_HUB_COUNT: Final = 19
REPORTED_BUSINESS_LINE_COUNT: Final = 6

# The retired hub ordinal is written numerically, and its codes are derived,
# so that no active product source file contains the forbidden literal itself.
# That keeps the active-source guard
# (tests/domain/architecture/test_forbidden_hub_code_source_guard.py) free of
# per-file allowlists: any literal occurrence under backend/app or
# frontend/src is a defect by definition, with no exception to reason about.
RETIRED_HUB_ORDINAL: Final = 12
_RETIRED_HUB_CODE: Final = f"IH-{RETIRED_HUB_ORDINAL}"
_RETIRED_HUB_SUBCODES: Final = 4

FORBIDDEN_HUB_CODES: Final[frozenset[str]] = frozenset(
    (
        _RETIRED_HUB_CODE,
        *(
            f"{_RETIRED_HUB_CODE}.{ordinal}"
            for ordinal in range(1, _RETIRED_HUB_SUBCODES + 1)
        ),
    )
)

_HUBS_BY_CODE: Final[Mapping[str, IntelligenceHub]] = MappingProxyType(
    {hub.code: hub for hub in INTELLIGENCE_HUBS}
)

CANONICAL_HUB_CODES: Final[frozenset[str]] = frozenset(_HUBS_BY_CODE)


def is_canonical_hub(code: str) -> bool:
    """Return whether ``code`` is one of the twelve canonical hub codes."""

    return code in _HUBS_BY_CODE


def assert_canonical_hub(code: str) -> None:
    """Raise unless ``code`` is one of the twelve canonical hub codes.

    Raises:
        ForbiddenIntelligenceHubError: for a code in ``FORBIDDEN_HUB_CODES``,
            which never existed in the canonical architecture.
        UnknownIntelligenceHubError: for any other non-canonical code.
    """

    if code in FORBIDDEN_HUB_CODES:
        raise ForbiddenIntelligenceHubError(
            f"Hub code {code} does not exist in the canonical architecture. "
            f"There are {INTELLIGENCE_HUB_COUNT} Intelligence Hubs, IH-00 to IH-11."
        )
    if code not in _HUBS_BY_CODE:
        raise UnknownIntelligenceHubError(f"Unknown Intelligence Hub code {code}.")


def get_intelligence_hub(code: str) -> IntelligenceHub:
    """Return the canonical hub for ``code``, or raise if it is not canonical."""

    assert_canonical_hub(code)
    return _HUBS_BY_CODE[code]


def get_reported_business_line(code: str) -> ReportedBusinessLine:
    """Return the reported line for ``code``, or raise if it is unknown."""

    line = REPORTED_BUSINESS_LINES.get(code)
    if line is None:
        raise UnknownIntelligenceHubError(f"Unknown reported business line {code}.")
    return line


def iter_operating_hubs() -> tuple[tuple[str, OperatingHub], ...]:
    """Return every operating hub paired with its owning Intelligence Hub code."""

    return tuple(
        (hub.code, operating_hub)
        for hub in INTELLIGENCE_HUBS
        for operating_hub in hub.operating_hubs
    )
