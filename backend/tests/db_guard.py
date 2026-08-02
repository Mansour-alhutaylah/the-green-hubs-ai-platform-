"""Fail-closed safety guard for the isolated integration-test database.

This module deliberately has no dependency on ``app`` configuration.  It
validates ``GH_TEST_DATABASE_URL`` before that value is copied into
``DATABASE_URL`` and before the application's import-time engine is built.
No exception message includes a connection URL or credential-bearing field.
"""

from __future__ import annotations

import os
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

TEST_DATABASE_MARKER = "GH_SIP_DISPOSABLE_TEST_DB_DO_NOT_CREATE_ELSEWHERE"
TEST_DATABASE_MARKER_TABLE = "gh_disposable_test_database"
EXPECTED_ALEMBIC_HEAD = "da0298a9c722"
EXPECTED_EXISTING_INTEGRATION_CASES = 144
REQUIRED_DATABASE_SUFFIX = "_test"

LOCAL_TEST_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "test-postgres"})
FORBIDDEN_HOST_FRAGMENTS = (
    "supabase",
    "pooler",
    "rds.amazonaws",
    "neon.tech",
    "azure.com",
    "render.com",
    "railway.app",
    "planetscale",
)
EXPECTED_APPLICATION_TABLES = frozenset(
    {
        "organizations",
        "users",
        "engagements",
        "documents",
        "extracted_text",
        "ai_analysis_results",
        "document_chunks",
        "document_chunk_embeddings",
        "analysis_runs",
        "analysis_source_references",
    }
)
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


class UnsafeTestDatabaseError(RuntimeError):
    """Raised before an unsafe or unproven integration target is used."""


@dataclass(frozen=True)
class TestDatabaseTarget:
    url: str
    host: str
    port: int
    database: str
    is_remote: bool


@dataclass(frozen=True)
class DatabaseProof:
    current_database: str
    marker: str | None
    migration_heads: frozenset[str]
    vector_version: str | None
    server_version: str
    public_tables: frozenset[str]


@dataclass(frozen=True)
class IntegrationOutcome:
    selected: int
    passed: int
    failed: int
    errors: int
    skipped: int

    @property
    def executed(self) -> int:
        return self.passed + self.failed + self.errors


def _enabled(value: str | None) -> bool:
    return bool(value and value.strip().lower() in _TRUE_VALUES)


def validate_test_database_target(
    database_url: str | None,
    *,
    integration_mode: str | None,
    environment: str | None,
    allow_remote: bool = False,
    allowed_remote_hosts: Collection[str] = (),
) -> TestDatabaseTarget:
    """Validate every static property before any connection is attempted."""

    if not _enabled(integration_mode):
        raise UnsafeTestDatabaseError(
            "Explicit integration-test mode is required; database target was not used."
        )
    if not database_url:
        raise UnsafeTestDatabaseError(
            "GH_TEST_DATABASE_URL is required; configured application databases are never used."
        )

    normalized_environment = (environment or "").strip().lower()
    if normalized_environment in {"production", "prod", "staging", "stage"}:
        raise UnsafeTestDatabaseError(
            "Production and staging environments are forbidden for integration tests."
        )
    if normalized_environment != "test":
        raise UnsafeTestDatabaseError(
            "ENVIRONMENT must be explicitly set to test for integration tests."
        )

    try:
        parsed = urlsplit(database_url)
        host = (parsed.hostname or "").lower()
        port = parsed.port or 5432
    except ValueError as exc:
        raise UnsafeTestDatabaseError(
            "Integration database URL is invalid; target was not used."
        ) from exc

    if parsed.scheme.lower() != "postgresql+asyncpg":
        raise UnsafeTestDatabaseError(
            "Integration database must use the postgresql+asyncpg scheme."
        )
    if not host:
        raise UnsafeTestDatabaseError("Integration database host is missing; target was not used.")

    database = unquote(parsed.path.lstrip("/"))
    if not database or "/" in database or not database.lower().endswith(REQUIRED_DATABASE_SUFFIX):
        raise UnsafeTestDatabaseError(
            "Integration database name must be explicitly test-specific."
        )

    if any(fragment in host for fragment in FORBIDDEN_HOST_FRAGMENTS):
        raise UnsafeTestDatabaseError(
            "Shared or managed database hosts are forbidden for integration tests."
        )

    normalized_remote_hosts = {candidate.strip().lower() for candidate in allowed_remote_hosts}
    is_remote = host not in LOCAL_TEST_HOSTS
    if is_remote and (not allow_remote or host not in normalized_remote_hosts):
        raise UnsafeTestDatabaseError(
            "Remote integration database host is not explicitly approved."
        )

    return TestDatabaseTarget(
        url=database_url,
        host=host,
        port=port,
        database=database,
        is_remote=is_remote,
    )


def load_test_database_target(
    environ: Mapping[str, str] | None = None,
) -> TestDatabaseTarget:
    values = os.environ if environ is None else environ
    allowed_remote_hosts = values.get("GH_TEST_ALLOWED_REMOTE_HOSTS", "").split(",")
    return validate_test_database_target(
        values.get("GH_TEST_DATABASE_URL"),
        integration_mode=values.get("GH_INTEGRATION_TEST_MODE"),
        environment=values.get("ENVIRONMENT"),
        allow_remote=_enabled(values.get("GH_TEST_ALLOW_REMOTE_HOST")),
        allowed_remote_hosts=allowed_remote_hosts,
    )


def configure_test_process_environment(target: TestDatabaseTarget) -> None:
    """Override only this process before any ``app`` import occurs."""

    os.environ["DATABASE_URL"] = target.url
    os.environ["ENVIRONMENT"] = "test"
    os.environ["DEBUG"] = "false"


def assert_database_proof(
    target: TestDatabaseTarget,
    proof: DatabaseProof,
    *,
    require_migrations: bool,
) -> None:
    """Validate positive in-database evidence without exposing the URL."""

    if proof.current_database != target.database:
        raise UnsafeTestDatabaseError(
            "Connected database identity does not match the guarded test target."
        )
    if proof.marker != TEST_DATABASE_MARKER:
        raise UnsafeTestDatabaseError(
            "Disposable test-database marker is missing or invalid; refusing database access."
        )
    if not require_migrations:
        return
    if proof.migration_heads != frozenset({EXPECTED_ALEMBIC_HEAD}):
        raise UnsafeTestDatabaseError(
            "Expected Alembic migration state is absent from the isolated test database."
        )
    if proof.vector_version is None:
        raise UnsafeTestDatabaseError(
            "pgvector is not installed in the isolated test database."
        )
    missing_tables = EXPECTED_APPLICATION_TABLES - proof.public_tables
    if missing_tables:
        raise UnsafeTestDatabaseError(
            "Expected application tables are absent from the isolated test database."
        )


async def inspect_database(target: TestDatabaseTarget) -> DatabaseProof:
    """Read the marker, migration state, extension, and table inventory."""

    engine = create_async_engine(target.url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            current_database = str(await connection.scalar(text("SELECT current_database()")))
            marker_table = await connection.scalar(
                text("SELECT to_regclass('public.gh_disposable_test_database')::text")
            )
            marker = None
            if marker_table is not None:
                marker = await connection.scalar(
                    text(
                        "SELECT marker FROM gh_disposable_test_database "
                        "WHERE marker = :expected_marker"
                    ),
                    {"expected_marker": TEST_DATABASE_MARKER},
                )

            alembic_table = await connection.scalar(
                text("SELECT to_regclass('public.alembic_version')::text")
            )
            migration_heads: frozenset[str] = frozenset()
            if alembic_table is not None:
                result = await connection.execute(text("SELECT version_num FROM alembic_version"))
                migration_heads = frozenset(str(row[0]) for row in result)

            vector_version = await connection.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            )
            server_version = str(await connection.scalar(text("SHOW server_version")))
            table_result = await connection.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' ORDER BY tablename"
                )
            )
            public_tables = frozenset(str(row[0]) for row in table_result)
    except UnsafeTestDatabaseError:
        raise
    except Exception as exc:
        raise UnsafeTestDatabaseError(
            "Could not verify the isolated test database; target details were redacted."
        ) from exc
    finally:
        await engine.dispose()

    return DatabaseProof(
        current_database=current_database,
        marker=str(marker) if marker is not None else None,
        migration_heads=migration_heads,
        vector_version=str(vector_version) if vector_version is not None else None,
        server_version=server_version,
        public_tables=public_tables,
    )


async def verify_isolated_database(
    target: TestDatabaseTarget,
    *,
    require_migrations: bool,
) -> DatabaseProof:
    proof = await inspect_database(target)
    assert_database_proof(target, proof, require_migrations=require_migrations)
    return proof


def assert_integration_collection(
    *,
    collected: int,
    existing_cases: int,
) -> None:
    if collected <= 0:
        raise UnsafeTestDatabaseError(
            "Integration collection produced zero tests; the gate cannot pass."
        )
    if existing_cases != EXPECTED_EXISTING_INTEGRATION_CASES:
        raise UnsafeTestDatabaseError(
            "Existing integration-case count changed; reconcile the collection before running."
        )


def assert_meaningful_integration_outcome(outcome: IntegrationOutcome) -> None:
    if outcome.selected <= 0:
        raise UnsafeTestDatabaseError(
            "Integration run selected zero tests; the gate cannot pass."
        )
    if outcome.executed <= 0 or outcome.skipped == outcome.selected:
        raise UnsafeTestDatabaseError(
            "Integration run executed zero tests or skipped every selected test; the gate failed."
        )
    if outcome.failed or outcome.errors:
        raise UnsafeTestDatabaseError(
            "Integration run reported failures or errors; the gate failed."
        )
