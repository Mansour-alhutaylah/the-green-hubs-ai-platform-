"""A domain with no backend can never advertise a functional control.

The point of this guard is the failure mode it prevents: an interface that
offers upload, query, analysis, calculation or approval for a domain whose
server side does not exist.
"""

from dataclasses import FrozenInstanceError

import pytest

from app.domain.architecture import (
    APPROVED_MVP_DOMAINS,
    AVAILABLE_MESSAGE,
    NOT_BUILT_MESSAGE,
    PRODUCT_DOMAINS,
    ActivationState,
    BuildState,
    DomainAction,
    ProductDomain,
    build_capability,
    domain_offers,
    get_domain_capability,
    get_intelligence_hub,
    is_approved_mvp_domain,
)

EXPECTED_MVP_DOMAINS = frozenset({"esg", "carbon", "energy", "pmo"})

EXPECTED_DOMAIN_TO_HUB = {
    "esg": "IH-02",
    "carbon": "IH-03",
    "energy": "IH-04",
    "pmo": "IH-07",
}


def test_the_four_approved_mvp_domains_are_recognised() -> None:
    assert APPROVED_MVP_DOMAINS == EXPECTED_MVP_DOMAINS
    assert frozenset(PRODUCT_DOMAINS) == EXPECTED_MVP_DOMAINS

    for domain in EXPECTED_MVP_DOMAINS:
        assert is_approved_mvp_domain(domain)


def test_domain_names_are_matched_case_insensitively() -> None:
    assert is_approved_mvp_domain("  ESG ")
    assert get_domain_capability("  ESG ").domain == "esg"


def test_each_mvp_domain_maps_to_its_canonical_intelligence_hub() -> None:
    for domain, hub_code in EXPECTED_DOMAIN_TO_HUB.items():
        capability = get_domain_capability(domain)

        assert capability.intelligence_hub == hub_code
        assert get_intelligence_hub(hub_code).code == hub_code


@pytest.mark.parametrize("domain", sorted(EXPECTED_MVP_DOMAINS))
def test_an_approved_mvp_domain_is_not_automatically_production(domain: str) -> None:
    capability = get_domain_capability(domain)

    assert capability.build_state is not BuildState.PRODUCTION
    assert capability.build_state is BuildState.REFERENCE
    assert capability.available is False


@pytest.mark.parametrize("domain", sorted(EXPECTED_MVP_DOMAINS) + ["water", "unknown"])
def test_a_domain_without_backend_capability_is_reported_as_unavailable(
    domain: str,
) -> None:
    capability = get_domain_capability(domain)

    assert capability.available is False
    assert capability.build_state is BuildState.REFERENCE
    assert capability.message == NOT_BUILT_MESSAGE
    assert "not yet" in capability.message


@pytest.mark.parametrize("domain", sorted(EXPECTED_MVP_DOMAINS) + ["water", "unknown"])
@pytest.mark.parametrize("action", list(DomainAction))
def test_an_unavailable_domain_advertises_no_action(
    domain: str, action: DomainAction
) -> None:
    capability = get_domain_capability(domain)

    assert capability.offered_actions == frozenset()
    assert capability.offers(action) is False


def test_an_unregistered_domain_is_refused_rather_than_guessed() -> None:
    capability = get_domain_capability("hub-zero")

    assert capability.available is False
    assert capability.intelligence_hub is None
    assert capability.offered_actions == frozenset()


def _domain_declaring_every_action(build_state: BuildState) -> ProductDomain:
    return ProductDomain(
        key="esg",
        intelligence_hub="IH-02",
        build_state=build_state,
        activation_state=ActivationState.ACTIVE,
        offered_actions=frozenset(DomainAction),
    )


def test_declared_actions_are_suppressed_while_a_domain_is_unbuilt() -> None:
    """A Reference domain stays inert even if every action is declared."""

    declared = _domain_declaring_every_action(BuildState.REFERENCE)

    capability = build_capability(declared)

    assert declared.offered_actions == frozenset(DomainAction)
    assert capability.available is False
    assert capability.offered_actions == frozenset()
    assert capability.message == NOT_BUILT_MESSAGE
    for action in DomainAction:
        assert capability.offers(action) is False


@pytest.mark.parametrize("build_state", [BuildState.IN_BUILD, BuildState.PRODUCTION])
def test_only_a_built_domain_may_offer_a_declared_action(
    build_state: BuildState,
) -> None:
    """The guard refuses by build state, so it must also stop refusing."""

    capability = build_capability(_domain_declaring_every_action(build_state))

    assert capability.available is True
    assert capability.message == AVAILABLE_MESSAGE
    for action in DomainAction:
        assert capability.offers(action) is True


def test_a_built_domain_still_offers_only_what_it_declares() -> None:
    partially_declared = ProductDomain(
        key="esg",
        intelligence_hub="IH-02",
        build_state=BuildState.IN_BUILD,
        activation_state=ActivationState.ACTIVE,
        offered_actions=frozenset({DomainAction.QUERY}),
    )

    capability = build_capability(partially_declared)

    assert capability.offers(DomainAction.QUERY) is True
    assert capability.offers(DomainAction.UPLOAD) is False
    assert capability.offers(DomainAction.CALCULATION) is False


def test_domain_offers_matches_the_capability_result() -> None:
    for domain in sorted(EXPECTED_MVP_DOMAINS) + ["water", "unknown"]:
        for action in DomainAction:
            assert domain_offers(domain, action) is False


def test_commercial_activation_is_not_technical_readiness() -> None:
    """Every MVP domain is commercially Active but technically Reference."""

    for domain in EXPECTED_MVP_DOMAINS:
        capability = get_domain_capability(domain)

        assert capability.activation_state.value == "active"
        assert capability.available is False


def test_capability_results_are_immutable() -> None:
    capability = get_domain_capability("carbon")

    with pytest.raises(FrozenInstanceError):
        capability.available = True  # type: ignore[misc]

    assert not hasattr(capability, "__dict__")


def test_product_domain_registry_is_protected_from_runtime_mutation() -> None:
    with pytest.raises(TypeError):
        PRODUCT_DOMAINS["water"] = PRODUCT_DOMAINS["esg"]  # type: ignore[index]

    assert frozenset(PRODUCT_DOMAINS) == EXPECTED_MVP_DOMAINS
