# Phase 1 MVP Slice 1 Canonical Architecture Design

Evidence IDs: **EV-ARC-CANON-01**, **EV-ARC-CAP-01**

Date: 2026-08-03 (Asia/Riyadh)

Branch: `feat/mvp-canonical-architecture-registry`

Starting commit: `01c769fe1a1c2b889bb0d4f9cb46a240b0442e8a`

Controlling source: Founder Blueprint MASTER v3.0.17, effective 1 August 2026.

## Why this folder

`06-release-evidence/` is already partitioned by programme (`foundation/` holds
the Phase 1A slices). The Trusted Document Intelligence MVP is a separate
programme, so its records sit in a sibling `mvp/` folder using the same
`<Phase>_<Slice>_<Topic>.md` file convention. No new hierarchy was invented.

## Scope

Slice 1 establishes one typed, tested source of truth for the approved
architecture. It adds no product feature, page, route, endpoint, table,
migration or dependency, and changes no authentication, authorization,
evidence, retrieval or audit behaviour.

## Canonical register

`backend/app/domain/architecture/registry.py` holds twelve Intelligence Hubs,
IH-00 to IH-11, governing nineteen operating hubs, consolidated into six
reported business lines.

| Hub | Name | Reported line | Operating hubs (activation state) |
|---|---|---|---|
| IH-00 | Zero Intelligence Hub | *(none)* | Green Zero Hub (active) |
| IH-01 | Consulting & Transformation | BU-06 | Green Consulting Hub (active); Green Digital Transformation Hub (incubating) |
| IH-02 | ESG Intelligence | BU-06 | Green ESG Hub (active) |
| IH-03 | Carbon Intelligence | BU-02 | Green Carbon Hub (active) |
| IH-04 | Energy Intelligence | BU-02 | Green Energy Hub (active) |
| IH-05 | Water Intelligence | BU-03 | Green Water Hub (incubating); Green Water Delivery Hub (planned) |
| IH-06 | Asset & Field Intelligence | BU-01 | Green Technology Hub (active); Green Materials Hub (planned) |
| IH-07 | PMO Intelligence | BU-01 | PMO Hub (active); Green Project Management Hub (incubating) |
| IH-08 | AI Intelligence | BU-05 | Green AI Hub (active) |
| IH-09 | Knowledge & Innovation | BU-05 | R&D Hub (planned); Center of Knowledge Hub (incubating); Green Training Hub (incubating) |
| IH-10 | Finance Intelligence | BU-06 | Green Finance Hub (incubating) |
| IH-11 | Social Impact Intelligence | BU-04 | Green Social Impact Hub (incubating); Green Nonprofit Transformation Hub (incubating) |

Operating-hub count: 1+2+1+1+1+2+2+2+1+3+1+2 = **19**.

Reported lines: BU-01 PMO & Execution, BU-02 Energy, Carbon & Climate,
BU-03 Water, BU-04 Social Impact & Local Content, BU-05 AI & Platform,
BU-06 Advisory & Transformation.

IH-00 is a governance layer and deliberately carries no reported revenue line.
Revenue-share percentages are **not** modelled: Slice 1 has no use for them, so
inventing them here would create a second, unreconciled financial source.

## Rejection behaviour

`assert_canonical_hub` raises `ForbiddenIntelligenceHubError` for the retired
twelfth-hub family and `UnknownIntelligenceHubError` for any other
non-canonical code. The forbidden subclass extends the unknown one, so a caller
that only cares that a code is not canonical catches a single base type. Both
extend the existing `app.core.exceptions.ValidationError`, following the
repository rule that domain and service errors subclass `AppError` rather than
raising HTTP exceptions outside the API layer.

## Two states, never conflated

Conflating commercial intent with technical readiness is how an interface ends
up offering a control that leads nowhere, so the two are modelled separately:

- `ActivationState` (active / incubating / planned) is the Blueprint's
  **commercial** state — what the business has decided to sell.
- `BuildState` (reference / in_build / production) is the **technical** state of
  this repository — what actually exists behind the interface.

Only `BuildState` can unlock a control.

## Approved MVP domains and their evidenced state

ESG, Carbon, Energy and PMO are registered as the four approved MVP domains.
All four are `BuildState.REFERENCE`, assigned from repository evidence rather
than from Blueprint ambition:

- No ESG, Carbon, Energy or PMO route, service, schema, table or calculation
  exists in `backend/app`; a repository-wide search returned only incidental
  vocabulary in docstrings and the generic analysis prompt.
- The only domain page in the interface is Carbon, an explicit `placeholder:
  true` navigation entry rendering `ComingSoonPage`. ESG, Energy and PMO have
  no route, navigation entry or page at all.

All four are commercially `active` and technically `reference` at the same
time. That is the honest position today, and the registry states it rather than
smoothing it over.

## The capability gate

`get_domain_capability(domain)` is the single gate. A domain that is not built
returns `available=False`, an empty action set, and a message saying it is not
yet built. Declared actions on an unbuilt domain are **dropped in
`build_capability`, not trusted**, so a mistaken declaration cannot reach the
interface. An unregistered domain name is refused by default rather than
guessed.

`DomainAction` covers upload, query, analysis, calculation and approval — the
five controls that must never be offered without a backend.

## Active-source guard

`backend/tests/domain/architecture/test_forbidden_hub_code_source_guard.py`
fails if the retired hub code is defined or exposed in active runtime product
source. It runs inside the standard `pytest -m "not integration"` CI job, so no
workflow change was needed.

Scanned: `backend/app`, `frontend/src`, `project-config`, `database`.

Excluded: tests (including the guard itself), `__tests__` / `__mocks__`
directories, `*.test.*` / `*.spec.*` / `test_*` / `conftest.py` files,
governance and audit records, documentation, generated output, build artifacts,
vendored dependencies, virtual environments and binary assets.

Also excluded: `backend/migrations`. Historical migrations legitimately carry
explanatory prose, and failing on an old comment is exactly the over-broad
behaviour this guard is meant to avoid. That boundary should be revisited if a
seed or fixture path that creates product records is ever added there.

Because the guard has no per-file allowlist, active product source never spells
the retired code out — not even in prose. `registry.py` derives it from
`RETIRED_HUB_ORDINAL` instead. Tests use the literal freely. This convention is
recorded in the `registry.py` module docstring.

## Verification that the guard is not vacuous

Three properties are covered by their own cases: the resolved repository roots
exist, more than one hundred real product files are actually read from both
`backend` and `frontend`, and synthetic registry entries, navigation items and
seed records are detected. Separately, a temporary file containing the
forbidden literal was written into `backend/app` during development; the guard
failed with the exact path and line, and the file was removed.

## Scope limitations

This slice does not deliver server-side authorization, tenant hardening,
evidence verification, page-level citations, prompt-injection defences, human
answer approval, tamper-evident audit, or the Golden Journey. It does not make
any domain available. It is the register those slices will be checked against.
