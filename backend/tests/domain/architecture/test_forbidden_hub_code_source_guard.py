"""Active-source guard: the retired hub code must never reach the product.

The registry already rejects the retired IH-12 family at runtime. This guard
covers the other half of the risk: someone re-introducing it as a *definition*
or *exposure* -- a registry entry, a navigation item, a route mapping, an
enabled domain configuration, or a seed record -- somewhere the interface can
show it.

Scope is deliberately narrow, because a repository-wide text scan would fail
on the very files that prove the code is rejected:

- Scanned: active runtime product source and active product configuration.
- Not scanned: tests (including this guard), governance and audit records,
  documentation, attached reference material, generated output, vendored
  dependencies, build artifacts and virtual environments.
- Not scanned: ``backend/migrations``. Historical migrations legitimately
  carry explanatory comments, and failing on old prose is exactly the
  over-broad behaviour this guard avoids. Revisit that boundary if a seed or
  fixture path that creates product records is ever added there.

Active product source therefore never spells the retired code out, not even
in prose -- ``registry.py`` derives it from ``RETIRED_HUB_ORDINAL``. That
convention is what lets this guard run with no per-file allowlist.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Iterable, Iterator

import pytest

from app.domain.architecture import FORBIDDEN_HUB_CODES, RETIRED_HUB_ORDINAL

REPO_ROOT: Final = Path(__file__).resolve().parents[4]

ACTIVE_SOURCE_ROOTS: Final[tuple[str, ...]] = (
    "backend/app",
    "frontend/src",
    "project-config",
    "database",
)

EXCLUDED_DIRECTORY_NAMES: Final[frozenset[str]] = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__mocks__",
        "__pycache__",
        "__tests__",
        "build",
        "coverage",
        "dist",
        "e2e",
        "node_modules",
        "test",
        "tests",
        "venv",
    }
)

EXCLUDED_FILE_SUFFIXES: Final[frozenset[str]] = frozenset(
    {
        ".avif",
        ".eot",
        ".gif",
        ".gz",
        ".ico",
        ".jpeg",
        ".jpg",
        ".map",
        ".mp4",
        ".otf",
        ".pdf",
        ".png",
        ".ttf",
        ".webp",
        ".woff",
        ".woff2",
        ".zip",
    }
)

_MAX_SCANNED_BYTES: Final = 2 * 1024 * 1024

RETIRED_HUB_CODE_PATTERN: Final = re.compile(
    rf"\bIH[-_ ]?{RETIRED_HUB_ORDINAL}\b", re.IGNORECASE
)


@dataclass(frozen=True)
class ForbiddenCodeFinding:
    path: Path
    line_number: int
    line: str


def _is_test_file(path: Path) -> bool:
    name = path.name
    return (
        name.startswith("test_")
        or name == "conftest.py"
        or ".test." in name
        or ".spec." in name
    )


def iter_scannable_files(roots: Iterable[Path]) -> Iterator[Path]:
    """Yield every active product file under ``roots``."""

    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if EXCLUDED_DIRECTORY_NAMES.intersection(path.relative_to(root).parts[:-1]):
                continue
            if path.suffix.lower() in EXCLUDED_FILE_SUFFIXES:
                continue
            if _is_test_file(path):
                continue
            yield path


def scan_for_retired_hub_code(roots: Iterable[Path]) -> list[ForbiddenCodeFinding]:
    """Return every retired-hub-code occurrence in active product source."""

    findings: list[ForbiddenCodeFinding] = []
    for path in iter_scannable_files(roots):
        try:
            if path.stat().st_size > _MAX_SCANNED_BYTES:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            if RETIRED_HUB_CODE_PATTERN.search(line):
                findings.append(ForbiddenCodeFinding(path, line_number, line.strip()))
    return findings


def _active_source_roots() -> tuple[Path, ...]:
    return tuple(REPO_ROOT / relative for relative in ACTIVE_SOURCE_ROOTS)


def test_the_guard_resolves_the_real_repository_roots() -> None:
    """A wrong path would make the scan pass vacuously."""

    assert (REPO_ROOT / "backend" / "app").is_dir()
    assert (REPO_ROOT / "frontend" / "src").is_dir()


def test_the_guard_actually_reads_active_product_source() -> None:
    scanned = list(iter_scannable_files(_active_source_roots()))
    scanned_parts = {path.relative_to(REPO_ROOT).parts[0] for path in scanned}

    assert len(scanned) > 100
    assert {"backend", "frontend"} <= scanned_parts


def test_active_product_source_defines_no_retired_hub_code() -> None:
    findings = scan_for_retired_hub_code(_active_source_roots())

    assert findings == [], "\n".join(
        f"{finding.path.relative_to(REPO_ROOT)}:{finding.line_number}: {finding.line}"
        for finding in findings
    )


def test_the_guard_excludes_test_directories_and_files() -> None:
    scanned = {path.name for path in iter_scannable_files(_active_source_roots())}

    assert not any(name.startswith("test_") for name in scanned)
    assert not any(".test." in name or ".spec." in name for name in scanned)


def test_the_guard_detects_a_forbidden_registry_entry(tmp_path: Path) -> None:
    source = tmp_path / "app" / "registry.py"
    source.parent.mkdir(parents=True)
    source.write_text('HUBS = ("IH-11", "IH-12")\n', encoding="utf-8")

    findings = scan_for_retired_hub_code([tmp_path])

    assert len(findings) == 1
    assert findings[0].path == source
    assert findings[0].line_number == 1


def test_the_guard_detects_a_forbidden_navigation_item(tmp_path: Path) -> None:
    source = tmp_path / "src" / "navConfig.ts"
    source.parent.mkdir(parents=True)
    source.write_text("export const NAV = [{ id: 'IH-12.4' }];\n", encoding="utf-8")

    assert len(scan_for_retired_hub_code([tmp_path])) == 1


def test_the_guard_detects_a_forbidden_seed_record(tmp_path: Path) -> None:
    source = tmp_path / "seed.json"
    source.write_text('{"hub_code": "ih_12", "enabled": true}\n', encoding="utf-8")

    assert len(scan_for_retired_hub_code([tmp_path])) == 1


@pytest.mark.parametrize("code", sorted(FORBIDDEN_HUB_CODES))
def test_every_forbidden_code_is_detected(tmp_path: Path, code: str) -> None:
    source = tmp_path / "module.py"
    source.write_text(f'HUB = "{code}"\n', encoding="utf-8")

    assert len(scan_for_retired_hub_code([tmp_path])) == 1


@pytest.mark.parametrize("text", ["IH12", "ih-12", "IH_12", "IH 12"])
def test_spelling_variants_are_detected(tmp_path: Path, text: str) -> None:
    source = tmp_path / "module.py"
    source.write_text(f'HUB = "{text}"\n', encoding="utf-8")

    assert len(scan_for_retired_hub_code([tmp_path])) == 1


@pytest.mark.parametrize("text", ["IH-11", "IH-1", "IH-120", "BUILD-1234"])
def test_canonical_and_unrelated_codes_are_not_flagged(
    tmp_path: Path, text: str
) -> None:
    source = tmp_path / "module.py"
    source.write_text(f'HUB = "{text}"\n', encoding="utf-8")

    assert scan_for_retired_hub_code([tmp_path]) == []


def test_test_only_rejection_literals_do_not_fail_the_guard(tmp_path: Path) -> None:
    """Proving rejection requires the literal; that must never trip the guard."""

    (tmp_path / "__tests__").mkdir()
    (tmp_path / "__tests__" / "nav.ts").write_text(
        "expect(hubs).not.toContain('IH-12');\n", encoding="utf-8"
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "navConfig.test.ts").write_text(
        "expect(NAV).not.toContain('IH-12');\n", encoding="utf-8"
    )
    (tmp_path / "src" / "navConfig.spec.tsx").write_text(
        "expect(NAV).not.toContain('IH-12');\n", encoding="utf-8"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "helpers.py").write_text(
        'RETIRED = "IH-12"\n', encoding="utf-8"
    )
    (tmp_path / "test_registry.py").write_text(
        'assert_canonical_hub("IH-12")\n', encoding="utf-8"
    )
    (tmp_path / "conftest.py").write_text('CODE = "IH-12"\n', encoding="utf-8")

    assert scan_for_retired_hub_code([tmp_path]) == []


def test_generated_vendored_and_build_output_is_not_scanned(tmp_path: Path) -> None:
    for directory in ("node_modules", "dist", "__pycache__", ".venv", "coverage"):
        (tmp_path / directory).mkdir()
        (tmp_path / directory / "bundle.js").write_text(
            "var hub = 'IH-12';\n", encoding="utf-8"
        )

    assert scan_for_retired_hub_code([tmp_path]) == []


def test_binary_assets_are_not_scanned(tmp_path: Path) -> None:
    (tmp_path / "logo.png").write_bytes(b"IH-12")

    assert scan_for_retired_hub_code([tmp_path]) == []


def test_a_missing_root_is_skipped_rather_than_failing(tmp_path: Path) -> None:
    assert scan_for_retired_hub_code([tmp_path / "does-not-exist"]) == []
