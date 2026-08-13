"""Drift and secret controls on the reviewed n8n workflow export.

The export is the only durable record of what the orchestrator actually
runs, and n8n's editor lets anyone change a live workflow without
touching this repository. These tests are what turn "the workflow must
not gain a database node" from a rule someone has to remember into a
build failure.

Two properties are enforced:

1. **No secret and no credential value.** Founder decision (Gate 1): the
   HMAC secret lives only in the platform secret store, and nothing --
   export, prompt, log, document or response -- may carry it.
2. **No forbidden capability.** The health check is Level 0. A Postgres
   node, a Supabase node, an AI node, a Drive node, a messaging node or
   an Execute Command node appearing here would mean the deployed
   workflow had quietly acquired an authority the foundation withholds.

Deliberately structural, not semantic: the scan reads the file, so it
catches a pasted-in credential regardless of which node type carries it.
"""

import json
import re
from pathlib import Path
from typing import Any, Final, Iterator

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parents[3]
EXPORT_DIR: Final = (
    REPO_ROOT / "project-governance" / "07-aios" / "n8n-workflow-exports"
)
HEALTH_CHECK_EXPORT: Final = EXPORT_DIR / "nora-health-check" / "workflow.json"

#: Node types the foundation phase forbids outright. Matched on the node
#: `type` field and, as defence in depth, anywhere in the raw text.
FORBIDDEN_NODE_TYPE_FRAGMENTS: Final[tuple[str, ...]] = (
    "postgres",
    "supabase",
    "mysql",
    "mongodb",
    "redis",
    "googleDrive",
    "googleSheets",
    "microsoftOneDrive",
    "microsoftSharePoint",
    "gmail",
    "emailSend",
    "sendEmail",
    "telegram",
    "slack",
    "twilio",
    "whatsApp",
    "executeCommand",
    # A sub-workflow call is a capability escape: it would let a
    # reviewed workflow reach an unreviewed one.
    "executeWorkflow",
    "toolWorkflow",
    "toolCode",
    "aiTransform",
    "mcpClient",
    "ssh",
    "ftp",
    "readWriteFile",
    "readBinaryFile",
    "writeBinaryFile",
    "openAi",
    "lmChat",
    "embeddings",
    "vectorStore",
    "agent",
)

#: Patterns that would indicate a real secret or connection string got
#: pasted into the export.
FORBIDDEN_VALUE_PATTERNS: Final[tuple[tuple[str, str], ...]] = (
    (r"postgres(?:ql)?(?:\+\w+)?://", "a PostgreSQL connection string"),
    (r"mysql://", "a MySQL connection string"),
    (r"mongodb(?:\+srv)?://", "a MongoDB connection string"),
    (r"\bsk-[A-Za-z0-9]{16,}", "an OpenAI-style API key"),
    (r"\bsk-or-v1-", "an OpenRouter API key"),
    (r"\beyJ[A-Za-z0-9_-]{20,}\.", "a JWT or Supabase service-role key"),
    (r"service_role", "a Supabase service-role reference"),
    (r"\bAKIA[0-9A-Z]{16}\b", "an AWS access key id"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "a private key"),
    (r"\bghp_[A-Za-z0-9]{20,}", "a GitHub token"),
    (r"\bxox[baprs]-[A-Za-z0-9-]{10,}", "a Slack token"),
)

#: The only hosts the export may reference. The n8n instance's own domain
#: is allowed because a webhook path may legitimately name it; anything
#: else is an unexpected external destination.
ALLOWED_URL_FRAGMENTS: Final[tuple[str, ...]] = (
    "thegreenhubs.app.n8n.cloud",
    "your-api-host",  # the documented placeholder hint
)


def _export_files() -> list[Path]:
    if not EXPORT_DIR.is_dir():
        return []
    return sorted(EXPORT_DIR.rglob("*.json"))


def _iter_nodes(document: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for node in document.get("nodes", []):
        if isinstance(node, dict):
            yield node


# ---------------------------------------------------------------------------
# The guard must be looking at real files
# ---------------------------------------------------------------------------


def test_the_health_check_export_exists() -> None:
    """A missing export would make every scan below pass vacuously."""

    assert HEALTH_CHECK_EXPORT.is_file(), f"missing export at {HEALTH_CHECK_EXPORT}"
    assert _export_files(), "no workflow exports found to scan"


def test_the_export_is_valid_json_and_names_the_workflow() -> None:
    document = json.loads(HEALTH_CHECK_EXPORT.read_text(encoding="utf-8"))
    assert document["name"] == "GH-AIOS / NORA / Health Check"


# ---------------------------------------------------------------------------
# Activation state
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("export", _export_files(), ids=lambda p: p.parent.name)
def test_no_exported_workflow_is_marked_active(export: Path) -> None:
    """Activation is a Gate 10 Founder decision. An export committed as
    active is either a mistake or an activation nobody approved."""

    document = json.loads(export.read_text(encoding="utf-8"))
    assert document.get("active") is False, f"{export.name} is marked active"


# ---------------------------------------------------------------------------
# Forbidden capabilities
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("export", _export_files(), ids=lambda p: p.parent.name)
def test_no_export_declares_a_forbidden_node_type(export: Path) -> None:
    document = json.loads(export.read_text(encoding="utf-8"))
    for node in _iter_nodes(document):
        node_type = str(node.get("type", ""))
        for fragment in FORBIDDEN_NODE_TYPE_FRAGMENTS:
            assert fragment.lower() not in node_type.lower(), (
                f"{export.name} node {node.get('name')!r} is a {fragment} node; "
                f"the foundation phase grants no such capability"
            )


@pytest.mark.parametrize("export", _export_files(), ids=lambda p: p.parent.name)
def test_no_export_mentions_a_forbidden_node_type_anywhere(export: Path) -> None:
    """Defence in depth: catches a forbidden node smuggled in somewhere
    other than a top-level ``type`` field."""

    raw = export.read_text(encoding="utf-8").lower()
    for fragment in FORBIDDEN_NODE_TYPE_FRAGMENTS:
        needle = f"n8n-nodes-base.{fragment}".lower()
        assert needle not in raw, f"{export.name} references {needle}"


@pytest.mark.parametrize("export", _export_files(), ids=lambda p: p.parent.name)
def test_no_export_carries_a_credential_reference(export: Path) -> None:
    """No node may hold a credential at all in the foundation phase --
    not a database one, not a provider one, not any."""

    document = json.loads(export.read_text(encoding="utf-8"))
    for node in _iter_nodes(document):
        assert not node.get("credentials"), (
            f"{export.name} node {node.get('name')!r} carries a credential reference"
        )


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("export", _export_files(), ids=lambda p: p.parent.name)
def test_no_export_contains_a_secret_shaped_value(export: Path) -> None:
    raw = export.read_text(encoding="utf-8")
    for pattern, description in FORBIDDEN_VALUE_PATTERNS:
        match = re.search(pattern, raw)
        assert match is None, f"{export.name} appears to contain {description}"


@pytest.mark.parametrize("export", _export_files(), ids=lambda p: p.parent.name)
def test_no_export_contains_the_signing_test_secret(export: Path) -> None:
    """Even the published test literal must not reach an export -- a
    value that looks configured invites someone to configure it."""

    fixture = json.loads(
        (REPO_ROOT / "backend" / "tests" / "fixtures" / "aios_signature_vectors.json").read_text(
            encoding="utf-8"
        )
    )
    raw = export.read_text(encoding="utf-8")
    assert fixture["secret_utf8"] not in raw


@pytest.mark.parametrize("export", _export_files(), ids=lambda p: p.parent.name)
def test_no_export_computes_an_hmac_inside_n8n(export: Path) -> None:
    """The whole point of the gateway-verification design: n8n forwards,
    FastAPI verifies. An HMAC computed inside a node would mean a secret
    had to be there to compute it with."""

    raw = export.read_text(encoding="utf-8").lower()
    for marker in ("createhmac", "crypto.", "$vars.", "$env."):
        assert marker not in raw, (
            f"{export.name} contains {marker!r} -- the signing secret must never "
            f"enter n8n; verification happens in FastAPI"
        )


# ---------------------------------------------------------------------------
# External destinations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("export", _export_files(), ids=lambda p: p.parent.name)
def test_no_export_references_an_unexpected_external_url(export: Path) -> None:
    """The only outbound request is to the FastAPI verification endpoint,
    which is an explicit unset placeholder rather than a configured host."""

    raw = export.read_text(encoding="utf-8")
    for url in re.findall(r"https?://[^\s\"'\\<>]+", raw):
        assert any(fragment in url for fragment in ALLOWED_URL_FRAGMENTS), (
            f"{export.name} references unexpected external URL {url!r}"
        )


@pytest.mark.parametrize("export", _export_files(), ids=lambda p: p.parent.name)
def test_no_outbound_url_is_dynamically_computed(export: Path) -> None:
    """A URL built from an expression is a destination the review cannot
    see -- it would be resolved at runtime from data, which is exactly
    the caller-controlled destination the boundary forbids. An n8n
    expression is stored with a leading ``=``.

    This closes the gap the plain-text URL scan leaves: an expression
    such as ``={{ $json.callback }}`` contains no ``https://`` at all, so
    the allow-list scan alone would never see it.
    """

    document = json.loads(export.read_text(encoding="utf-8"))
    for node in _iter_nodes(document):
        if node.get("type") != "n8n-nodes-base.httpRequest":
            continue
        url = node.get("parameters", {}).get("url", "")
        assert isinstance(url, str)
        assert not url.startswith("="), (
            f"{export.name} node {node.get('name')!r} computes its URL from an "
            f"expression; the destination must come from configuration only"
        )


def test_the_verification_url_is_an_unset_placeholder() -> None:
    """It must not be a real host: the AIOS deployment URL is a Gate 10
    configuration step, and a committed URL would be promoted by accident."""

    document = json.loads(HEALTH_CHECK_EXPORT.read_text(encoding="utf-8"))
    verification = next(
        node
        for node in _iter_nodes(document)
        if node["name"] == "Request FastAPI Verification"
    )
    url = verification["parameters"]["url"]
    assert url.startswith("<__PLACEHOLDER_VALUE__"), url


# ---------------------------------------------------------------------------
# The shape the health check must keep
# ---------------------------------------------------------------------------


def test_the_webhook_captures_the_raw_body() -> None:
    """Without this the digest cannot be reproduced, and the whole
    signature scheme silently degrades to signing re-serialized JSON."""

    document = json.loads(HEALTH_CHECK_EXPORT.read_text(encoding="utf-8"))
    webhook = next(
        node for node in _iter_nodes(document) if node["type"] == "n8n-nodes-base.webhook"
    )
    assert webhook["parameters"]["options"]["rawBody"] is True
    assert webhook["parameters"]["httpMethod"] == "POST"
    assert webhook["parameters"]["path"] == "gh-aios/v1/nora/health-check"


def test_the_webhook_path_is_versioned() -> None:
    document = json.loads(HEALTH_CHECK_EXPORT.read_text(encoding="utf-8"))
    webhook = next(
        node for node in _iter_nodes(document) if node["type"] == "n8n-nodes-base.webhook"
    )
    assert "/v1/" in f"/{webhook['parameters']['path']}"


def test_the_export_matches_the_registered_webhook_path() -> None:
    """The export and the application's workflow registry must describe
    the same endpoint; a drift here is a 404 in production."""

    from app.domain.aios.workflows import NORA_HEALTH_CHECK, resolve_workflow

    workflow = resolve_workflow(NORA_HEALTH_CHECK)
    assert workflow is not None

    document = json.loads(HEALTH_CHECK_EXPORT.read_text(encoding="utf-8"))
    webhook = next(
        node for node in _iter_nodes(document) if node["type"] == "n8n-nodes-base.webhook"
    )
    assert workflow.webhook_path == f"/webhook/{webhook['parameters']['path']}"


def test_the_only_outbound_request_is_the_verification_call() -> None:
    document = json.loads(HEALTH_CHECK_EXPORT.read_text(encoding="utf-8"))
    http_nodes = [
        node
        for node in _iter_nodes(document)
        if node["type"] == "n8n-nodes-base.httpRequest"
    ]
    assert len(http_nodes) == 1
    assert http_nodes[0]["name"] == "Request FastAPI Verification"


def test_the_reviewed_code_node_source_is_version_controlled() -> None:
    """Code that exists only as a string inside an export cannot be
    tested by anything. The reviewed source and its parity test are what
    make the JavaScript half of the protocol provable."""

    directory = HEALTH_CHECK_EXPORT.parent
    assert (directory / "capture-raw-request.js").is_file()
    assert (directory / "aios-signature.mjs").is_file()
    assert (directory / "aios-signature.test.mjs").is_file()
    # The export/review/promotion procedure covers every workflow, so it
    # lives once at the exports root rather than per workflow.
    assert (EXPORT_DIR / "README.md").is_file()
