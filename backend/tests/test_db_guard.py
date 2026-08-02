from __future__ import annotations

from typing import Any

import pytest

from tests.db_guard import (
    DatabaseProof,
    IntegrationOutcome,
    TEST_DATABASE_MARKER,
    UnsafeTestDatabaseError,
    assert_database_proof,
    assert_integration_collection,
    assert_meaningful_integration_outcome,
    validate_test_database_target,
)

VALID_URL = "postgresql+asyncpg://synthetic:synthetic@127.0.0.1:55432/green_hubs_test"


def validate(url: str | None = VALID_URL, **overrides: Any):
    arguments: dict[str, Any] = {
        "integration_mode": "true",
        "environment": "test",
    }
    arguments.update(overrides)
    return validate_test_database_target(url, **arguments)


def test_valid_isolated_test_database_is_accepted() -> None:
    target = validate()
    assert target.database == "green_hubs_test"
    assert target.host == "127.0.0.1"
    assert target.is_remote is False


def test_missing_database_url_is_rejected() -> None:
    with pytest.raises(UnsafeTestDatabaseError, match="GH_TEST_DATABASE_URL"):
        validate(None)


def test_missing_explicit_integration_mode_is_rejected() -> None:
    with pytest.raises(UnsafeTestDatabaseError, match="Explicit integration-test mode"):
        validate(integration_mode=None)


def test_non_test_database_name_is_rejected() -> None:
    with pytest.raises(UnsafeTestDatabaseError, match="test-specific"):
        validate("postgresql+asyncpg://synthetic:synthetic@127.0.0.1/shared")


def test_supabase_host_is_rejected() -> None:
    with pytest.raises(UnsafeTestDatabaseError, match="managed database"):
        validate("postgresql+asyncpg://synthetic:synthetic@db.example.supabase.co/app_test")


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_production_and_staging_environments_are_rejected(environment: str) -> None:
    with pytest.raises(UnsafeTestDatabaseError, match="forbidden"):
        validate(environment=environment)


def test_unapproved_remote_host_is_rejected() -> None:
    with pytest.raises(UnsafeTestDatabaseError, match="not explicitly approved"):
        validate("postgresql+asyncpg://synthetic:synthetic@db.internal.example/app_test")


def test_unsupported_database_scheme_is_rejected() -> None:
    with pytest.raises(UnsafeTestDatabaseError, match=r"postgresql\+asyncpg"):
        validate("postgresql://synthetic:synthetic@127.0.0.1:55432/green_hubs_test")


def test_missing_marker_is_rejected() -> None:
    target = validate()
    proof = DatabaseProof(
        current_database=target.database,
        marker=None,
        migration_heads=frozenset(),
        vector_version=None,
        server_version="synthetic",
        public_tables=frozenset(),
    )
    with pytest.raises(UnsafeTestDatabaseError, match="marker"):
        assert_database_proof(target, proof, require_migrations=False)


def test_error_output_redacts_credentials_and_query_parameters() -> None:
    secret_url = (
        "postgresql+asyncpg://private-user:private-password@"
        "db.example.supabase.co/app_test?access_token=private-token"
    )
    with pytest.raises(UnsafeTestDatabaseError) as error:
        validate(secret_url)
    message = str(error.value)
    assert "private-user" not in message
    assert "private-password" not in message
    assert "private-token" not in message
    assert secret_url not in message


def test_official_collection_rejects_zero_tests() -> None:
    with pytest.raises(UnsafeTestDatabaseError, match="zero tests"):
        assert_integration_collection(collected=0, existing_cases=0)


def test_official_run_rejects_all_skipped_tests() -> None:
    with pytest.raises(UnsafeTestDatabaseError, match="skipped every"):
        assert_meaningful_integration_outcome(
            IntegrationOutcome(selected=144, passed=0, failed=0, errors=0, skipped=144)
        )


def test_migration_state_is_required_after_bootstrap() -> None:
    target = validate()
    proof = DatabaseProof(
        current_database=target.database,
        marker=TEST_DATABASE_MARKER,
        migration_heads=frozenset(),
        vector_version="0.8.1",
        server_version="synthetic",
        public_tables=frozenset(),
    )
    with pytest.raises(UnsafeTestDatabaseError, match="Alembic"):
        assert_database_proof(target, proof, require_migrations=True)
