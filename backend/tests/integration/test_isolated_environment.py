from __future__ import annotations

import pytest
from sqlalchemy import text

from app.infrastructure.db.session import engine
from tests.db_guard import EXPECTED_ALEMBIC_HEAD, TEST_DATABASE_MARKER

pytestmark = pytest.mark.integration


async def test_isolated_database_marker_and_identity() -> None:
    async with engine.connect() as connection:
        database = await connection.scalar(text("SELECT current_database()"))
        marker = await connection.scalar(
            text("SELECT marker FROM gh_disposable_test_database WHERE marker = :marker"),
            {"marker": TEST_DATABASE_MARKER},
        )
    assert str(database).endswith("_test")
    assert marker == TEST_DATABASE_MARKER


async def test_isolated_database_migrations_and_pgvector() -> None:
    async with engine.connect() as connection:
        head = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        vector_version = await connection.scalar(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )
    assert head == EXPECTED_ALEMBIC_HEAD
    assert vector_version


async def test_pgvector_accepts_expected_embedding_dimension() -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text("CREATE TEMP TABLE slice1_vector_probe (embedding vector(1536) NOT NULL)")
        )
        await connection.execute(
            text("INSERT INTO slice1_vector_probe (embedding) VALUES (:embedding)"),
            {"embedding": "[1," + ",".join(["0"] * 1535) + "]"},
        )
        distance = await connection.scalar(
            text("SELECT embedding <=> embedding FROM slice1_vector_probe LIMIT 1")
        )
    assert float(distance) == 0.0
