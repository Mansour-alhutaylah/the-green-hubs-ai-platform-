"""The ``audit_events`` table, exercised against real PostgreSQL.

Phase 1A Slice 3. The unit suite
(``tests/services/test_audit_service.py``) proves the service's rules
against a fake repository; nothing there touches SQL. This module proves
the half only a real database can: that the migration's CHECK
constraints reject what they claim to, that the tenant-scoped read
returns one organization's rows and no other's, and -- the finding that
matters most for how this table may be described -- what the
application's database role can actually do to a row after it is
written.

Evidence items EV-AUD-03b (database-level append-only enforcement) and
the tenant half of EV-AUD-02.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.domain.entities.audit_event import ActorType, AuditEvent, AuditResult
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.repositories.audit_event import SQLAlchemyAuditEventRepository
from tests.db_guard import TEST_DATABASE_MARKER

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def _require_the_disposable_test_database() -> None:
    """Refuse to write audit rows into anything not proved disposable."""

    async with AsyncSessionLocal() as session:
        marker = await session.scalar(
            text("SELECT marker FROM gh_disposable_test_database LIMIT 1")
        )
    if marker != TEST_DATABASE_MARKER:
        pytest.fail("Refusing to run: this is not the disposable test database.")


@pytest.fixture
async def cleanup_correlation_ids() -> list[str]:
    """Track correlation ids and delete only those rows afterwards.

    Deletion happens through a raw statement on a separate session, not
    through the repository -- the repository has no delete path, which is
    the property under test.
    """

    tracked: list[str] = []
    yield tracked
    if tracked:
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("DELETE FROM audit_events WHERE correlation_id = ANY(:ids)"),
                {"ids": tracked},
            )
            await session.commit()


def _event(correlation_id: str, **overrides) -> AuditEvent:
    defaults = dict(
        action="document.upload",
        actor_type=ActorType.USER,
        result=AuditResult.SUCCESS,
        correlation_id=correlation_id,
        actor_user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
    )
    defaults.update(overrides)
    return AuditEvent(**defaults)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# The row round-trips, and the server assigns what it should
# --------------------------------------------------------------------------


async def test_an_appended_event_is_persisted_with_server_assigned_fields(
    cleanup_correlation_ids: list[str],
) -> None:
    correlation_id = str(uuid.uuid4())
    cleanup_correlation_ids.append(correlation_id)
    organization_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        repository = SQLAlchemyAuditEventRepository(session)
        await repository.append(_event(correlation_id, organization_id=organization_id))
        await session.commit()

    async with AsyncSessionLocal() as session:
        repository = SQLAlchemyAuditEventRepository(session)
        events = await repository.list_for_organization(
            organization_id=organization_id, limit=10, offset=0
        )

    assert len(events) == 1
    stored = events[0]
    # The database, not the application, assigns identity and time.
    assert stored.id is not None
    assert stored.recorded_seq is not None
    assert stored.occurred_at is not None
    assert stored.occurred_at.tzinfo is not None, "occurred_at must be timezone-aware"
    assert stored.event_schema_version == 1
    assert stored.action == "document.upload"
    assert stored.result is AuditResult.SUCCESS


async def test_append_does_not_commit_on_its_own(
    cleanup_correlation_ids: list[str],
) -> None:
    """A staged event must vanish if the caller's transaction rolls back.

    This is what makes ``record_in_transaction`` honest: no SUCCESS event
    can outlive the business change it describes.
    """

    correlation_id = str(uuid.uuid4())
    cleanup_correlation_ids.append(correlation_id)
    organization_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        repository = SQLAlchemyAuditEventRepository(session)
        await repository.append(_event(correlation_id, organization_id=organization_id))
        await session.rollback()

    async with AsyncSessionLocal() as session:
        repository = SQLAlchemyAuditEventRepository(session)
        events = await repository.list_for_organization(
            organization_id=organization_id, limit=10, offset=0
        )

    assert events == []


# --------------------------------------------------------------------------
# Tenant scoping
# --------------------------------------------------------------------------


async def test_the_scoped_read_returns_only_the_callers_organization(
    cleanup_correlation_ids: list[str],
) -> None:
    own_organization = uuid.uuid4()
    foreign_organization = uuid.uuid4()
    own_correlation = str(uuid.uuid4())
    foreign_correlation = str(uuid.uuid4())
    cleanup_correlation_ids.extend([own_correlation, foreign_correlation])

    async with AsyncSessionLocal() as session:
        repository = SQLAlchemyAuditEventRepository(session)
        await repository.append(
            _event(own_correlation, organization_id=own_organization, action="own.event")
        )
        await repository.append(
            _event(
                foreign_correlation,
                organization_id=foreign_organization,
                action="foreign.event",
            )
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        repository = SQLAlchemyAuditEventRepository(session)
        events = await repository.list_for_organization(
            organization_id=own_organization, limit=50, offset=0
        )
        count = await repository.count_for_organization(
            organization_id=own_organization
        )

    assert count == 1
    assert [event.action for event in events] == ["own.event"]
    assert all(event.organization_id == own_organization for event in events)


async def test_a_null_organization_event_is_invisible_to_every_tenant_read(
    cleanup_correlation_ids: list[str],
) -> None:
    """Pre-tenant failures belong to no tenant and must surface in none.

    Placing an unattributable event inside some organization's view would
    be a cross-tenant leak in the opposite direction.
    """

    correlation_id = str(uuid.uuid4())
    cleanup_correlation_ids.append(correlation_id)
    some_organization = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        repository = SQLAlchemyAuditEventRepository(session)
        await repository.append(
            _event(
                correlation_id,
                organization_id=None,
                actor_type=ActorType.ANONYMOUS,
                actor_user_id=None,
                result=AuditResult.DENIED,
                action="auth.token_rejected",
            )
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        repository = SQLAlchemyAuditEventRepository(session)
        events = await repository.list_for_organization(
            organization_id=some_organization, limit=50, offset=0
        )

    assert events == []

    # But the row does exist -- it simply is not tenant-addressable.
    async with AsyncSessionLocal() as session:
        stored = await session.scalar(
            text("SELECT count(*) FROM audit_events WHERE correlation_id = :cid"),
            {"cid": correlation_id},
        )
    assert stored == 1


async def test_the_scoped_read_is_ordered_most_recent_first_and_paginates(
    cleanup_correlation_ids: list[str],
) -> None:
    organization_id = uuid.uuid4()
    correlation_id = str(uuid.uuid4())
    cleanup_correlation_ids.append(correlation_id)

    async with AsyncSessionLocal() as session:
        repository = SQLAlchemyAuditEventRepository(session)
        for index in range(5):
            await repository.append(
                _event(
                    correlation_id,
                    organization_id=organization_id,
                    action=f"event.{index}",
                )
            )
        await session.commit()

    async with AsyncSessionLocal() as session:
        repository = SQLAlchemyAuditEventRepository(session)
        first_page = await repository.list_for_organization(
            organization_id=organization_id, limit=2, offset=0
        )
        second_page = await repository.list_for_organization(
            organization_id=organization_id, limit=2, offset=2
        )
        total = await repository.count_for_organization(
            organization_id=organization_id
        )

    assert total == 5
    assert len(first_page) == 2
    assert len(second_page) == 2
    # Newest first, and pages must not overlap.
    assert first_page[0].action == "event.4"
    assert second_page[0].action == "event.2"
    assert {event.id for event in first_page}.isdisjoint(
        {event.id for event in second_page}
    )


# --------------------------------------------------------------------------
# The CHECK constraints actually reject
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("actor_type", "result", "constraint"),
    [
        ("SUPERUSER", "SUCCESS", "ck_audit_events_actor_type"),
        ("SYSTEM", "MAYBE", "ck_audit_events_result"),
    ],
)
async def test_an_out_of_catalog_value_is_rejected_by_the_database(
    actor_type: str, result: str, constraint: str
) -> None:
    from sqlalchemy.exc import IntegrityError

    async with AsyncSessionLocal() as session:
        with pytest.raises(IntegrityError) as excinfo:
            await session.execute(
                text(
                    "INSERT INTO audit_events "
                    "(actor_type, action, result, correlation_id) "
                    "VALUES (:actor_type, 'test.action', :result, :cid)"
                ),
                {
                    "actor_type": actor_type,
                    "result": result,
                    "cid": str(uuid.uuid4()),
                },
            )
            await session.commit()
        await session.rollback()

    assert constraint in str(excinfo.value)


async def test_a_user_attributed_row_without_an_actor_id_is_rejected() -> None:
    from sqlalchemy.exc import IntegrityError

    async with AsyncSessionLocal() as session:
        with pytest.raises(IntegrityError) as excinfo:
            await session.execute(
                text(
                    "INSERT INTO audit_events "
                    "(actor_type, action, result, correlation_id) "
                    "VALUES ('USER', 'test.action', 'SUCCESS', :cid)"
                ),
                {"cid": str(uuid.uuid4())},
            )
            await session.commit()
        await session.rollback()

    assert "ck_audit_events_user_actor_has_id" in str(excinfo.value)


# --------------------------------------------------------------------------
# EV-AUD-03b -- what the application role can actually do to a written row
# --------------------------------------------------------------------------


async def test_the_repository_offers_no_route_to_update_or_delete_a_row() -> None:
    """Layer 1: the mutation surface does not exist to be called.

    This is the honest, currently-true statement about append-only. It is
    a property of the code, not of the database.
    """

    assert not hasattr(SQLAlchemyAuditEventRepository, "update")
    assert not hasattr(SQLAlchemyAuditEventRepository, "delete")


async def test_records_the_application_roles_real_privileges_on_audit_events(
    cleanup_correlation_ids: list[str],
) -> None:
    """Layer 3 investigation, recorded as an executable finding.

    Phase 1A plan section 8.2 makes database-level append-only conditional
    on the application connecting as a role that is neither the table
    owner nor a superuser, and names determining that role an explicit
    Slice 3 task. This test performs that determination and asserts the
    result rather than assuming it, so the claim this codebase is allowed
    to make about immutability is derived from the database itself.

    It deliberately does **not** assert that UPDATE is blocked. On the
    current configuration it is not, and writing an assertion that passes
    only because the privilege happens to be revoked somewhere would turn
    a known gap into a green tick.
    """

    correlation_id = str(uuid.uuid4())
    cleanup_correlation_ids.append(correlation_id)

    async with AsyncSessionLocal() as session:
        repository = SQLAlchemyAuditEventRepository(session)
        await repository.append(_event(correlation_id))
        await session.commit()

    async with AsyncSessionLocal() as session:
        current_role = await session.scalar(text("SELECT current_user"))
        is_superuser = await session.scalar(
            text("SELECT usesuper FROM pg_user WHERE usename = current_user")
        )
        table_owner = await session.scalar(
            text(
                "SELECT tableowner FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename = 'audit_events'"
            )
        )
        can_update = await session.scalar(
            text("SELECT has_table_privilege(current_user, 'audit_events', 'UPDATE')")
        )
        can_delete = await session.scalar(
            text("SELECT has_table_privilege(current_user, 'audit_events', 'DELETE')")
        )

    owns_table = current_role == table_owner
    database_enforced = not bool(can_update) and not bool(can_delete)

    # The finding, stated so a reader of the test output learns the truth
    # rather than having to infer it.
    print(
        "\nEV-AUD-03b application role privileges on audit_events: "
        f"role={current_role} superuser={bool(is_superuser)} "
        f"table_owner={table_owner} owns_table={owns_table} "
        f"can_update={bool(can_update)} can_delete={bool(can_delete)} "
        f"database_enforced_append_only={database_enforced}"
    )

    # The one thing that must hold either way: if the role can still
    # UPDATE, then append-only is a code property only, and nothing may
    # call this table immutable or tamper-evident.
    if not database_enforced:
        assert owns_table or bool(is_superuser), (
            "The application role can UPDATE/DELETE audit_events without "
            "being the owner or a superuser, which means a plain GRANT is "
            "the cause and revoking it is straightforward."
        )
