"""The Slice 4 migration, exercised as a migration against real PostgreSQL.

This is the only place that proves what happens to rows that existed
*before* the evidence lifecycle did. Every other test creates its rows
against the current schema, where ``evidence_status``'s column default
already applies -- which proves the default is fail-closed, but says
nothing about the ``ALTER TABLE``.

So this module does the real thing, in order:

1. downgrade to ``a4f1c9d2e7b3``, the revision immediately before Slice
   4, at which point ``documents`` genuinely has no evidence columns;
2. insert a PROCESSED document there, using SQL that could not name an
   evidence column even if it wanted to;
3. upgrade through ``b7d41e0c9a52``;
4. assert the pre-existing row is now ``PENDING_REVIEW`` -- **not**
   ``VERIFIED``, and not carrying an invented reviewer or timestamp;
5. downgrade and upgrade once more, proving the migration is reversible
   and re-appliable rather than a one-way door.

Backfilling historical documents as approved evidence would be
fabricating the exact human decision this slice exists to record, so
"every legacy row lands unapproved" is a correctness property, not a
convenience.

Alembic runs as a subprocess, deliberately. ``migrations/env.py`` drives
an async engine through ``asyncio.run``, which cannot be called from
inside the already-running loop an async test lives in; the subprocess
is also the same canonical ``python -m alembic`` invocation the runbook
and CI use, so this exercises the real command rather than a
reimplementation of it.

The module is guarded twice over: it refuses to run unless
``tests.db_guard`` has already proved this is the disposable test
database, and its ``finally`` block always restores the schema to head
so a failure here cannot leave the database mid-migration for the rest
of the suite.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from app.infrastructure.db.session import AsyncSessionLocal, engine
from tests.db_guard import EXPECTED_ALEMBIC_HEAD, TEST_DATABASE_MARKER

pytestmark = pytest.mark.integration

BACKEND_ROOT = Path(__file__).resolve().parents[2]

#: The revision immediately before Slice 4. Asserted against the real
#: migration file below, so a rebase that renumbers the chain fails here
#: rather than silently testing the wrong upgrade.
SLICE_4_REVISION = "b7d41e0c9a52"
PREDECESSOR_REVISION = "a4f1c9d2e7b3"

EVIDENCE_COLUMNS = frozenset(
    {
        "evidence_status",
        "reviewed_by",
        "reviewed_at",
        "review_reason",
        "superseded_by_document_id",
    }
)


def _alembic(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the canonical Alembic CLI against the guarded test database.

    ``DATABASE_URL`` is whatever ``tests.db_guard`` already installed in
    this process's environment after proving the target is disposable --
    it is never read from ``.env`` here."""

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(BACKEND_ROOT)
    environment["ENVIRONMENT"] = "test"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=BACKEND_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"alembic {' '.join(arguments)} failed:\n{result.stdout}\n{result.stderr}"
    )
    return result


async def _current_revision() -> str | None:
    async with AsyncSessionLocal() as session:
        return await session.scalar(text("SELECT version_num FROM alembic_version"))


async def _documents_columns() -> set[str]:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'documents'"
                )
            )
        ).scalars().all()
    return set(rows)


@pytest.fixture(autouse=True)
async def _require_the_disposable_test_database() -> None:
    """Refuse to migrate anything that has not proved it is disposable.

    ``conftest`` already validated the target before the app imported;
    this re-reads the in-database marker immediately before a
    schema-mutating test, because this module is the only one that runs
    DDL against the whole database rather than its own rows."""

    async with engine.connect() as connection:
        marker = await connection.scalar(
            text("SELECT marker FROM gh_disposable_test_database WHERE marker = :marker"),
            {"marker": TEST_DATABASE_MARKER},
        )
        database = await connection.scalar(text("SELECT current_database()"))
    if marker != TEST_DATABASE_MARKER or not str(database).endswith("_test"):
        pytest.fail("refusing to run migrations against a non-disposable database", pytrace=False)


@pytest.fixture
async def restored_to_head():
    """Always leave the schema at head, whatever the test did."""

    yield
    _alembic("upgrade", "head")
    assert await _current_revision() == EXPECTED_ALEMBIC_HEAD


# ---------------------------------------------------------------------------
# The chain itself
# ---------------------------------------------------------------------------


def test_the_slice_4_migration_declares_the_expected_predecessor() -> None:
    """The revision identifiers this module depends on are real."""

    migration = (
        BACKEND_ROOT
        / "migrations"
        / "versions"
        / f"{SLICE_4_REVISION}_add_document_evidence_review_state.py"
    )

    source = migration.read_text(encoding="utf-8")
    assert f'revision: str = \'{SLICE_4_REVISION}\'' in source
    assert f'down_revision: Union[str, None] = \'{PREDECESSOR_REVISION}\'' in source


async def test_the_database_is_at_the_slice_4_head() -> None:
    assert EXPECTED_ALEMBIC_HEAD == SLICE_4_REVISION
    assert await _current_revision() == SLICE_4_REVISION


# ---------------------------------------------------------------------------
# The legacy-row guarantee
# ---------------------------------------------------------------------------


async def test_a_document_that_predates_the_migration_becomes_pending_review(
    restored_to_head,
) -> None:
    """The genuine pre-migration proof.

    The document is inserted while the schema is at
    ``a4f1c9d2e7b3`` -- there is no ``evidence_status`` column to set at
    that point -- and is only then carried through the Slice 4 upgrade."""

    organization_id = uuid.uuid4()
    engagement_id = uuid.uuid4()
    document_id = uuid.uuid4()

    _alembic("downgrade", PREDECESSOR_REVISION)
    assert await _current_revision() == PREDECESSOR_REVISION

    # At this revision the evidence columns do not exist at all.
    columns_before = await _documents_columns()
    assert columns_before.isdisjoint(EVIDENCE_COLUMNS), (
        f"evidence columns survived the downgrade: {columns_before & EVIDENCE_COLUMNS}"
    )

    async with AsyncSessionLocal() as session:
        await session.execute(
            text("INSERT INTO organizations (id, name) VALUES (:id, :name)"),
            {"id": organization_id, "name": "Slice4 Legacy Migration Org"},
        )
        await session.execute(
            text(
                "INSERT INTO engagements (id, organization_id, title) "
                "VALUES (:id, :organization_id, :title)"
            ),
            {
                "id": engagement_id,
                "organization_id": organization_id,
                "title": "Slice4 Legacy Migration Engagement",
            },
        )
        await session.execute(
            text(
                "INSERT INTO documents (id, filename, storage_path, processing_status, "
                "engagement_id) VALUES (:id, :filename, :path, 'PROCESSED', :engagement_id)"
            ),
            {
                "id": document_id,
                "filename": "pre-slice4-report.pdf",
                "path": f"slice4-legacy/{document_id}.pdf",
                "engagement_id": engagement_id,
            },
        )
        await session.commit()

    try:
        _alembic("upgrade", SLICE_4_REVISION)
        assert await _current_revision() == SLICE_4_REVISION

        async with AsyncSessionLocal() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT evidence_status, reviewed_by, reviewed_at, review_reason, "
                        "superseded_by_document_id FROM documents WHERE id = :id"
                    ),
                    {"id": document_id},
                )
            ).mappings().one()

        # The whole point: historical evidence is unapproved, never
        # backfilled as approved, and carries no invented provenance.
        assert row["evidence_status"] == "PENDING_REVIEW"
        assert row["evidence_status"] != "VERIFIED"
        assert row["reviewed_by"] is None
        assert row["reviewed_at"] is None
        assert row["review_reason"] is None
        assert row["superseded_by_document_id"] is None
    finally:
        async with AsyncSessionLocal() as session:
            for statement in (
                "DELETE FROM documents WHERE id = :document_id",
                "DELETE FROM engagements WHERE id = :engagement_id",
                "DELETE FROM organizations WHERE id = :organization_id",
            ):
                await session.execute(
                    text(statement),
                    {
                        "document_id": document_id,
                        "engagement_id": engagement_id,
                        "organization_id": organization_id,
                    },
                )
            await session.commit()


async def test_the_migration_is_reversible_and_reappliable(restored_to_head) -> None:
    """upgrade -> downgrade -> upgrade, with the schema inspected at each
    step. A migration that cannot be rolled back is a one-way door in a
    release process that assumes it is not."""

    assert EVIDENCE_COLUMNS <= await _documents_columns()

    _alembic("downgrade", PREDECESSOR_REVISION)
    assert await _current_revision() == PREDECESSOR_REVISION
    assert (await _documents_columns()).isdisjoint(EVIDENCE_COLUMNS)

    _alembic("upgrade", "head")
    assert await _current_revision() == SLICE_4_REVISION
    assert EVIDENCE_COLUMNS <= await _documents_columns()


# ---------------------------------------------------------------------------
# What the migration actually created
# ---------------------------------------------------------------------------


async def test_the_evidence_status_column_defaults_to_pending_review() -> None:
    async with AsyncSessionLocal() as session:
        default = await session.scalar(
            text(
                "SELECT column_default FROM information_schema.columns "
                "WHERE table_name = 'documents' AND column_name = 'evidence_status'"
            )
        )
        nullable = await session.scalar(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'documents' AND column_name = 'evidence_status'"
            )
        )

    assert "PENDING_REVIEW" in str(default)
    assert nullable == "NO"


@pytest.mark.parametrize(
    "constraint",
    [
        "ck_documents_evidence_status",
        "ck_documents_evidence_review_consistency",
        "ck_documents_review_reason_format",
        "ck_documents_not_superseded_by_self",
    ],
)
async def test_the_check_constraints_exist(constraint: str) -> None:
    async with AsyncSessionLocal() as session:
        found = await session.scalar(
            text(
                "SELECT conname FROM pg_constraint WHERE conname = :name "
                "AND conrelid = 'documents'::regclass AND contype = 'c'"
            ),
            {"name": constraint},
        )

    assert found == constraint


@pytest.mark.parametrize(
    "constraint",
    ["fk_documents_reviewed_by_users", "fk_documents_superseded_by_document"],
)
async def test_the_foreign_keys_exist(constraint: str) -> None:
    async with AsyncSessionLocal() as session:
        found = await session.scalar(
            text(
                "SELECT conname FROM pg_constraint WHERE conname = :name "
                "AND conrelid = 'documents'::regclass AND contype = 'f'"
            ),
            {"name": constraint},
        )

    assert found == constraint


async def test_the_evidence_status_index_exists() -> None:
    """The review queue filters on this across an organization's rows."""

    async with AsyncSessionLocal() as session:
        found = await session.scalar(
            text(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'documents' "
                "AND indexname = 'ix_documents_evidence_status'"
            )
        )

    assert found == "ix_documents_evidence_status"


async def test_a_reviewed_by_value_must_reference_a_real_user() -> None:
    """The foreign key is what stops a decision naming a reviewer who
    does not exist.

    The document under test is created here rather than borrowed from
    whatever happens to be in the table: an ``UPDATE ... WHERE id =
    (SELECT id FROM documents LIMIT 1)`` matches **zero rows** against a
    freshly migrated database, violates nothing, and would make this
    assertion pass for the wrong reason -- or, as CI found, fail with
    ``DID NOT RAISE``. Every row is removed again in ``finally``."""

    organization_id = uuid.uuid4()
    engagement_id = uuid.uuid4()
    document_id = uuid.uuid4()
    parameters = {
        "organization_id": organization_id,
        "engagement_id": engagement_id,
        "document_id": document_id,
    }

    async with AsyncSessionLocal() as setup_session:
        await setup_session.execute(
            text("INSERT INTO organizations (id, name) VALUES (:organization_id, :name)"),
            {**parameters, "name": "Slice4 Reviewer FK Org"},
        )
        await setup_session.execute(
            text(
                "INSERT INTO engagements (id, organization_id, title) "
                "VALUES (:engagement_id, :organization_id, :title)"
            ),
            {**parameters, "title": "Slice4 Reviewer FK Engagement"},
        )
        await setup_session.execute(
            text(
                "INSERT INTO documents (id, filename, storage_path, processing_status, "
                "engagement_id) VALUES (:document_id, :filename, :path, 'PROCESSED', "
                ":engagement_id)"
            ),
            {
                **parameters,
                "filename": "reviewer-fk.pdf",
                "path": f"slice4-reviewer-fk/{document_id}.pdf",
            },
        )
        await setup_session.commit()

    try:
        async with AsyncSessionLocal() as session:
            with pytest.raises(Exception) as excinfo:
                await session.execute(
                    text(
                        "UPDATE documents SET evidence_status = 'VERIFIED', "
                        "reviewed_by = :ghost, reviewed_at = now() "
                        "WHERE id = :document_id"
                    ),
                    {**parameters, "ghost": uuid.uuid4()},
                )
                await session.commit()
            message = str(excinfo.value).lower()
            assert "foreign key" in message or "violates" in message
            await session.rollback()

        # The refused write left the row exactly as it was.
        async with AsyncSessionLocal() as verify_session:
            status = await verify_session.scalar(
                text("SELECT evidence_status FROM documents WHERE id = :document_id"),
                parameters,
            )
        assert status == "PENDING_REVIEW"
    finally:
        async with AsyncSessionLocal() as cleanup_session:
            for statement in (
                "DELETE FROM documents WHERE id = :document_id",
                "DELETE FROM engagements WHERE id = :engagement_id",
                "DELETE FROM organizations WHERE id = :organization_id",
            ):
                await cleanup_session.execute(text(statement), parameters)
            await cleanup_session.commit()
