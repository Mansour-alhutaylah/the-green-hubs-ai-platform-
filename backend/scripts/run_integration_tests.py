"""Official fail-closed collection and execution path for integration tests."""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from tests.db_guard import (  # noqa: E402
    IntegrationOutcome,
    UnsafeTestDatabaseError,
    assert_integration_collection,
    assert_meaningful_integration_outcome,
    configure_test_process_environment,
    load_test_database_target,
    verify_isolated_database,
)

ENVIRONMENT_PROBE_MODULE = "tests/integration/test_isolated_environment.py"


def pytest_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(BACKEND_ROOT)
    # A loopback-only issuer satisfies app construction. Integration tests
    # replace JWKS fetches and storage/AI gateways; an accidental call cannot
    # reach Supabase or a paid provider.
    environment["SUPABASE_URL"] = "http://127.0.0.1:9"
    for key in (
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_JWT_SECRET",
        "SUPABASE_STORAGE_BUCKET",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        environment.pop(key, None)
    return environment


def pytest_base_command() -> list[str]:
    return [
        sys.executable,
        "-m",
        "pytest",
        "-c",
        str(BACKEND_ROOT / "pytest.ini"),
        str(BACKEND_ROOT / "tests"),
        "-m",
        "integration",
    ]


def collect() -> tuple[int, int]:
    result = subprocess.run(
        [*pytest_base_command(), "--collect-only", "-q"],
        cwd=REPOSITORY_ROOT,
        env=pytest_environment(),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise UnsafeTestDatabaseError("Integration collection failed; the gate cannot pass.")

    nodeids = [
        line.strip()
        for line in result.stdout.splitlines()
        if "::" in line and not line.lstrip().startswith(("=", "<"))
    ]
    existing_cases = sum(
        1 for nodeid in nodeids if ENVIRONMENT_PROBE_MODULE not in nodeid.replace("\\", "/")
    )
    assert_integration_collection(collected=len(nodeids), existing_cases=existing_cases)
    print(f"integration_collection={len(nodeids)} existing_cases={existing_cases}")
    return len(nodeids), existing_cases


def run() -> IntegrationOutcome:
    with tempfile.TemporaryDirectory(prefix="gh-integration-") as temp_directory:
        report = Path(temp_directory) / "pytest.xml"
        result = subprocess.run(
            [*pytest_base_command(), "-q", f"--junitxml={report}"],
            cwd=REPOSITORY_ROOT,
            env=pytest_environment(),
            check=False,
        )
        if not report.exists():
            raise UnsafeTestDatabaseError("Integration run produced no machine-readable result.")
        root = ET.parse(report).getroot()
        suite = root if root.tag == "testsuite" else root.find("testsuite")
        if suite is None:
            raise UnsafeTestDatabaseError("Integration result report contained no test suite.")
        selected = int(suite.attrib.get("tests", "0"))
        failures = int(suite.attrib.get("failures", "0"))
        errors = int(suite.attrib.get("errors", "0"))
        skipped = int(suite.attrib.get("skipped", "0"))
        outcome = IntegrationOutcome(
            selected=selected,
            passed=selected - failures - errors - skipped,
            failed=failures,
            errors=errors,
            skipped=skipped,
        )
        if result.returncode != 0 and not (outcome.failed or outcome.errors):
            raise UnsafeTestDatabaseError("Pytest failed outside a reported test case.")
        assert_meaningful_integration_outcome(outcome)
        print(
            "integration_result="
            f"selected:{outcome.selected} executed:{outcome.executed} "
            f"passed:{outcome.passed} failed:{outcome.failed} "
            f"errors:{outcome.errors} skipped:{outcome.skipped}"
        )
        return outcome


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("collect", "run", "all"), default="all", nargs="?")
    args = parser.parse_args()
    try:
        target = load_test_database_target()
        configure_test_process_environment(target)
        asyncio.run(verify_isolated_database(target, require_migrations=True))
        if args.action in {"collect", "all"}:
            collect()
        if args.action in {"run", "all"}:
            run()
    except UnsafeTestDatabaseError as exc:
        print(f"integration gate failure: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
