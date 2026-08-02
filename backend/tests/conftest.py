import os
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from tests.db_guard import (
    TestDatabaseTarget,
    UnsafeTestDatabaseError,
    configure_test_process_environment,
    load_test_database_target,
    verify_isolated_database,
)

_integration_target: TestDatabaseTarget | None = None


def _integration_requested(config: pytest.Config) -> bool:
    expression = str(config.getoption("markexpr") or "").lower()
    positive_marker_selection = "integration" in expression and "not integration" not in expression
    explicit_mode = os.environ.get("GH_INTEGRATION_TEST_MODE", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return positive_marker_selection or explicit_mode


def pytest_configure(config: pytest.Config) -> None:
    """Validate and install the test URL before application modules import."""

    global _integration_target
    if not _integration_requested(config):
        return
    try:
        _integration_target = load_test_database_target()
    except UnsafeTestDatabaseError as exc:
        raise pytest.UsageError(str(exc)) from exc
    configure_test_process_environment(_integration_target)


@pytest.fixture(scope="session", autouse=True)
async def isolated_integration_database_guard() -> None:
    """Require marker, migrations, and pgvector before integration tests run."""

    if _integration_target is None:
        return
    try:
        await verify_isolated_database(_integration_target, require_migrations=True)
    except UnsafeTestDatabaseError as exc:
        pytest.fail(str(exc), pytrace=False)


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    # Deliberately lazy: the integration target is installed before app.main
    # creates the process-wide database engine during test-module collection.
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
