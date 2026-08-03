"""The canonical architecture register cannot drift from the Blueprint.

Founder Blueprint MASTER v3.0.17: twelve Intelligence Hubs (IH-00 to IH-11)
governing nineteen operating hubs, consolidated into six reported business
lines. Every count here is asserted against a literal, not against a value
derived from the registry, so a silent addition or removal fails the build.
"""

from dataclasses import FrozenInstanceError

import pytest

from app.domain.architecture import (
    CANONICAL_HUB_CODES,
    FORBIDDEN_HUB_CODES,
    INTELLIGENCE_HUB_COUNT,
    INTELLIGENCE_HUBS,
    OPERATING_HUB_COUNT,
    REPORTED_BUSINESS_LINE_COUNT,
    REPORTED_BUSINESS_LINES,
    ActivationState,
    ForbiddenIntelligenceHubError,
    UnknownIntelligenceHubError,
    assert_canonical_hub,
    get_intelligence_hub,
    get_reported_business_line,
    is_canonical_hub,
    iter_operating_hubs,
)

EXPECTED_HUB_CODES = frozenset(
    {
        "IH-00",
        "IH-01",
        "IH-02",
        "IH-03",
        "IH-04",
        "IH-05",
        "IH-06",
        "IH-07",
        "IH-08",
        "IH-09",
        "IH-10",
        "IH-11",
    }
)

EXPECTED_BUSINESS_LINE_CODES = frozenset(
    {"BU-01", "BU-02", "BU-03", "BU-04", "BU-05", "BU-06"}
)

EXPECTED_HUB_TO_LINE = {
    "IH-00": None,
    "IH-01": "BU-06",
    "IH-02": "BU-06",
    "IH-03": "BU-02",
    "IH-04": "BU-02",
    "IH-05": "BU-03",
    "IH-06": "BU-01",
    "IH-07": "BU-01",
    "IH-08": "BU-05",
    "IH-09": "BU-05",
    "IH-10": "BU-06",
    "IH-11": "BU-04",
}


def test_there_are_exactly_twelve_intelligence_hubs() -> None:
    assert len(INTELLIGENCE_HUBS) == 12
    assert INTELLIGENCE_HUB_COUNT == 12


def test_canonical_codes_run_from_ih_00_to_ih_11() -> None:
    assert INTELLIGENCE_HUBS[0].code == "IH-00"
    assert INTELLIGENCE_HUBS[-1].code == "IH-11"


def test_the_exact_canonical_code_set_is_present() -> None:
    assert CANONICAL_HUB_CODES == EXPECTED_HUB_CODES


def test_no_duplicate_intelligence_hub_code_exists() -> None:
    codes = [hub.code for hub in INTELLIGENCE_HUBS]

    assert len(codes) == len(set(codes))


def test_there_are_exactly_nineteen_operating_hubs() -> None:
    assert OPERATING_HUB_COUNT == 19
    assert sum(len(hub.operating_hubs) for hub in INTELLIGENCE_HUBS) == 19
    assert len(iter_operating_hubs()) == 19


def test_no_operating_hub_belongs_to_more_than_one_intelligence_hub() -> None:
    names = [operating_hub.name for _, operating_hub in iter_operating_hubs()]

    assert len(names) == len(set(names))


def test_every_operating_hub_has_a_known_activation_state() -> None:
    for _, operating_hub in iter_operating_hubs():
        assert isinstance(operating_hub.activation_state, ActivationState)


def test_there_are_exactly_six_reported_business_lines() -> None:
    assert REPORTED_BUSINESS_LINE_COUNT == 6
    assert len(REPORTED_BUSINESS_LINES) == 6
    assert frozenset(REPORTED_BUSINESS_LINES) == EXPECTED_BUSINESS_LINE_CODES


def test_the_registry_cannot_silently_introduce_another_business_line() -> None:
    referenced = {
        hub.reported_line for hub in INTELLIGENCE_HUBS if hub.reported_line is not None
    }

    assert referenced <= EXPECTED_BUSINESS_LINE_CODES
    assert referenced == EXPECTED_BUSINESS_LINE_CODES


def test_every_hub_except_ih_00_maps_to_a_known_reported_line() -> None:
    for hub in INTELLIGENCE_HUBS:
        if hub.code == "IH-00":
            continue
        assert hub.reported_line is not None, hub.code
        assert hub.reported_line in REPORTED_BUSINESS_LINES, hub.code


def test_ih_00_has_no_reported_business_line() -> None:
    assert get_intelligence_hub("IH-00").reported_line is None


def test_hub_to_reported_line_mapping_matches_the_blueprint() -> None:
    actual = {hub.code: hub.reported_line for hub in INTELLIGENCE_HUBS}

    assert actual == EXPECTED_HUB_TO_LINE


def test_get_reported_business_line_returns_the_named_line() -> None:
    assert get_reported_business_line("BU-01").name == "PMO & Execution"


def test_get_reported_business_line_rejects_an_unknown_code() -> None:
    with pytest.raises(UnknownIntelligenceHubError):
        get_reported_business_line("BU-99")


@pytest.mark.parametrize("code", ["IH-12", "IH-12.1", "IH-12.2", "IH-12.3", "IH-12.4"])
def test_the_retired_hub_family_is_rejected(code: str) -> None:
    assert code in FORBIDDEN_HUB_CODES
    assert not is_canonical_hub(code)

    with pytest.raises(ForbiddenIntelligenceHubError) as excinfo:
        assert_canonical_hub(code)

    assert "does not exist in the canonical architecture" in str(excinfo.value)


def test_forbidden_codes_are_exactly_the_retired_family() -> None:
    assert FORBIDDEN_HUB_CODES == frozenset(
        {"IH-12", "IH-12.1", "IH-12.2", "IH-12.3", "IH-12.4"}
    )


def test_forbidden_codes_never_overlap_the_canonical_set() -> None:
    assert FORBIDDEN_HUB_CODES.isdisjoint(CANONICAL_HUB_CODES)


@pytest.mark.parametrize(
    "code", ["IH-99", "ih-01", "IH01", "", "BU-01", "IH-1", "IH-011"]
)
def test_unknown_hub_codes_are_rejected(code: str) -> None:
    assert not is_canonical_hub(code)

    with pytest.raises(UnknownIntelligenceHubError):
        assert_canonical_hub(code)


def test_a_retired_code_is_catchable_as_an_unknown_code() -> None:
    with pytest.raises(UnknownIntelligenceHubError):
        assert_canonical_hub("IH-12")


@pytest.mark.parametrize("code", sorted(EXPECTED_HUB_CODES))
def test_every_canonical_code_is_accepted(code: str) -> None:
    assert is_canonical_hub(code)
    assert assert_canonical_hub(code) is None
    assert get_intelligence_hub(code).code == code


def test_registry_entries_are_immutable() -> None:
    hub = INTELLIGENCE_HUBS[0]

    with pytest.raises(FrozenInstanceError):
        hub.code = "IH-99"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        hub.operating_hubs[0].name = "Renamed Hub"  # type: ignore[misc]

    assert not hasattr(hub, "__dict__")


def test_registry_collections_are_protected_from_runtime_mutation() -> None:
    with pytest.raises(TypeError):
        REPORTED_BUSINESS_LINES["BU-07"] = REPORTED_BUSINESS_LINES["BU-01"]  # type: ignore[index]

    assert isinstance(INTELLIGENCE_HUBS, tuple)
    assert isinstance(CANONICAL_HUB_CODES, frozenset)
    assert isinstance(FORBIDDEN_HUB_CODES, frozenset)
    assert len(REPORTED_BUSINESS_LINES) == 6
