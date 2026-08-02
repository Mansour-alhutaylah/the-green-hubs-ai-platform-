"""Manage and prove the disposable Slice 1 integration database."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from tests.db_guard import (  # noqa: E402
    UnsafeTestDatabaseError,
    configure_test_process_environment,
    load_test_database_target,
    verify_isolated_database,
)


async def bootstrap_marker() -> None:
    target = load_test_database_target()
    configure_test_process_environment(target)
    marker_sql = (BACKEND_ROOT / "tests" / "db" / "init" / "001_test_marker.sql").read_text(
        encoding="utf-8"
    )
    engine = create_async_engine(target.url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            for statement in marker_sql.split(";"):
                if statement.strip():
                    await connection.execute(text(statement))
    finally:
        await engine.dispose()
    await verify_isolated_database(target, require_migrations=False)
    print(f"marker=verified database={target.database} host={target.host} port={target.port}")


def migrate() -> None:
    target = load_test_database_target()
    configure_test_process_environment(target)
    asyncio.run(verify_isolated_database(target, require_migrations=False))

    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    command.upgrade(config, "head")
    print(f"migrations=applied database={target.database}")


async def verify() -> None:
    target = load_test_database_target()
    configure_test_process_environment(target)
    proof = await verify_isolated_database(target, require_migrations=True)
    print(f"database={proof.current_database} host={target.host} port={target.port}")
    print(f"postgresql={proof.server_version} pgvector={proof.vector_version}")
    print(f"alembic_heads={','.join(sorted(proof.migration_heads))}")
    print(f"marker=verified public_tables={len(proof.public_tables)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("bootstrap-marker", "migrate", "verify"))
    args = parser.parse_args()
    try:
        if args.action == "bootstrap-marker":
            asyncio.run(bootstrap_marker())
        elif args.action == "migrate":
            migrate()
        else:
            asyncio.run(verify())
    except UnsafeTestDatabaseError as exc:
        print(f"test database safety failure: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
