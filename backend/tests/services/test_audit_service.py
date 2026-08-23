"""Phase 1A Slice 3 -- the audit spine's behaviour and its guarantees.

Covers evidence items EV-AUD-03a (append-only by construction) and
EV-AUD-04 (the data-minimisation denylist fails loudly), plus the two
write modes of plan section 8.3.

No database is required: the repository is a fake that records what it
was asked to append, which is exactly the seam these tests need. The
database-level behaviour of the table -- that the CHECK constraints and
indexes exist and that migrations apply -- is a separate integration
concern.
"""

import inspect
import logging
from uuid import uuid4

import pytest

from app.domain.entities.audit_event import ActorType, AuditEvent, AuditResult
from app.domain.repositories.audit_event import IAuditEventRepository
from app.domain.repositories.base import IRepository
from app.infrastructure.repositories.audit_event import SQLAlchemyAuditEventRepository
from app.services.audit import (
    FORBIDDEN_PAYLOAD_KEY_FRAGMENTS,
    STATE_ALLOW_LIST,
    AuditService,
    ForbiddenAuditPayloadError,
    state_snapshot,
)


class FakeAuditEventRepository(IAuditEventRepository):
    def __init__(self, *, fail_on_append: bool = False) -> None:
        self.appended: list[AuditEvent] = []
        self._fail_on_append = fail_on_append

    async def append(self, event: AuditEvent) -> None:
        if self._fail_on_append:
            raise RuntimeError("simulated database failure")
        self.appended.append(event)

    async def list_for_organization(
        self, *, organization_id, limit, offset
    ) -> list[AuditEvent]:
        return []

    async def count_for_organization(self, *, organization_id) -> int:
        return 0


class FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def _event(**overrides) -> AuditEvent:
    defaults = dict(
        action="document.upload",
        actor_type=ActorType.USER,
        result=AuditResult.SUCCESS,
        correlation_id=str(uuid4()),
        actor_user_id=uuid4(),
        organization_id=uuid4(),
    )
    defaults.update(overrides)
    return AuditEvent(**defaults)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# EV-AUD-03a -- append-only is structural, not a convention
# --------------------------------------------------------------------------


def test_the_audit_repository_interface_exposes_no_mutation_methods() -> None:
    surface = {
        name
        for name, _ in inspect.getmembers(IAuditEventRepository, inspect.isfunction)
        if not name.startswith("_")
    }
    assert surface == {"append", "list_for_organization", "count_for_organization"}
    assert "update" not in surface
    assert "delete" not in surface


def test_the_audit_repository_does_not_inherit_the_generic_write_contract() -> None:
    # IRepository supplies update/delete; inheriting it would reintroduce
    # exactly the mutation surface this slice removes.
    assert not issubclass(IAuditEventRepository, IRepository)
    assert not issubclass(SQLAlchemyAuditEventRepository, IRepository)


def test_the_concrete_audit_repository_has_no_update_or_delete_attribute() -> None:
    assert not hasattr(SQLAlchemyAuditEventRepository, "update")
    assert not hasattr(SQLAlchemyAuditEventRepository, "delete")


def test_an_audit_event_cannot_be_mutated_after_construction() -> None:
    event = _event()
    with pytest.raises(Exception):
        event.action = "tampered"  # type: ignore[misc]


# --------------------------------------------------------------------------
# EV-AUD-04 -- the denylist raises rather than silently redacting
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "access_token",
        "api_key",
        "password",
        "client_secret",
        "authorization",
        "content",
        "extracted_text",
        "embedding",
        "prompt",
        "quoted_snippet",
    ],
)
async def test_a_forbidden_payload_key_raises_rather_than_being_redacted(
    forbidden_key: str,
) -> None:
    repository = FakeAuditEventRepository()
    service = AuditService(repository)

    with pytest.raises(ForbiddenAuditPayloadError) as excinfo:
        await service.record_in_transaction(
            _event(new_state={forbidden_key: "should never be recorded"})
        )

    assert forbidden_key in str(excinfo.value)
    # Nothing was written -- the failure is detected before the append.
    assert repository.appended == []


async def test_the_denylist_also_covers_the_previous_state_payload() -> None:
    repository = FakeAuditEventRepository()
    service = AuditService(repository)

    with pytest.raises(ForbiddenAuditPayloadError):
        await service.record_in_transaction(_event(previous_state={"api_key": "x"}))

    assert repository.appended == []


def test_the_denylist_matches_case_insensitively() -> None:
    repository = FakeAuditEventRepository()
    service = AuditService(repository)
    event = _event(new_state={"ACCESS_TOKEN": "x"})

    with pytest.raises(ForbiddenAuditPayloadError):
        service._validate(event)


@pytest.mark.parametrize(
    "payload",
    [
        {"metadata": {"access_token": "secret"}},
        {"items": [{"password": "hunter2"}]},
        {"a": {"b": {"c": {"api_key": "secret"}}}},
        {"outer": [{"inner": {"quoted_snippet": "document text"}}]},
        {"tuple_wrapped": ({"secret": "x"},)},
    ],
)
def test_a_forbidden_key_nested_at_any_depth_is_rejected(payload: dict) -> None:
    """A top-level-only scan was a real bypass; this is its regression.

    ``{"metadata": {"token": ...}}`` previously passed validation and
    would have been written to JSONB verbatim.
    """

    service = AuditService(FakeAuditEventRepository())
    with pytest.raises(ForbiddenAuditPayloadError):
        service._validate(_event(new_state=payload))


def test_the_reported_path_locates_the_offending_nested_key() -> None:
    service = AuditService(FakeAuditEventRepository())
    with pytest.raises(ForbiddenAuditPayloadError) as excinfo:
        service._validate(_event(new_state={"items": [{"password": "x"}]}))
    assert "items[0].password" in str(excinfo.value)


def test_a_payload_nested_past_the_depth_cap_is_refused_not_truncated() -> None:
    # A payload this service cannot fully inspect must not be recorded,
    # otherwise the cap itself becomes the bypass.
    deep: dict = {"leaf": "value"}
    for _ in range(12):
        deep = {"nest": deep}

    service = AuditService(FakeAuditEventRepository())
    with pytest.raises(ForbiddenAuditPayloadError) as excinfo:
        service._validate(_event(new_state=deep))
    assert "nests deeper" in str(excinfo.value)


def test_a_legitimate_nested_payload_without_forbidden_keys_is_accepted() -> None:
    # The recursive scan must not reject ordinary structured data.
    service = AuditService(FakeAuditEventRepository())
    validated = service._validate(
        _event(new_state={"engagement": {"id": "e1", "status": "ACTIVE"}})
    )
    assert validated.new_state == {"engagement": {"id": "e1", "status": "ACTIVE"}}


def test_a_string_value_containing_a_forbidden_word_is_not_a_false_positive() -> None:
    # The denylist governs keys, not values; rejecting on values would
    # make ordinary titles unrecordable.
    service = AuditService(FakeAuditEventRepository())
    validated = service._validate(
        _event(new_state={"title": "Quarterly content review"})
    )
    assert validated.new_state == {"title": "Quarterly content review"}


def test_every_documented_forbidden_fragment_is_actually_enforced() -> None:
    # Guards against a fragment being dropped from the set without the
    # tests noticing, which would silently widen what may be recorded.
    for fragment in FORBIDDEN_PAYLOAD_KEY_FRAGMENTS:
        service = AuditService(FakeAuditEventRepository())
        with pytest.raises(ForbiddenAuditPayloadError):
            service._validate(_event(new_state={fragment: "x"}))


# --------------------------------------------------------------------------
# The state allow-list
# --------------------------------------------------------------------------


def test_state_snapshot_keeps_only_allow_listed_fields() -> None:
    snapshot = state_snapshot(
        "engagement",
        {
            "id": "e1",
            "organization_id": "o1",
            "title": "Q3 review",
            "status": "ACTIVE",
            # None of the following are on the allow-list.
            "secret_notes": "confidential",
            "owner_email": "person@example.com",
        },
    )
    assert snapshot == {
        "id": "e1",
        "organization_id": "o1",
        "title": "Q3 review",
        "status": "ACTIVE",
    }


def test_state_snapshot_cannot_leak_a_field_by_passing_a_whole_entity_dict() -> None:
    snapshot = state_snapshot(
        "document",
        {
            "id": "d1",
            "filename": "report.pdf",
            "processing_status": "COMPLETED",
            "extracted_text": "the entire document body",
            "storage_path": "organizations/o/engagements/e/d.pdf",
        },
    )
    assert "extracted_text" not in snapshot
    assert "storage_path" not in snapshot


def test_state_snapshot_omits_absent_fields_rather_than_recording_null() -> None:
    snapshot = state_snapshot("organization", {"id": "o1"})
    assert snapshot == {"id": "o1"}
    assert "name" not in snapshot


def test_state_snapshot_serialises_uuids_so_the_payload_is_json_safe() -> None:
    identifier = uuid4()
    snapshot = state_snapshot("organization", {"id": identifier, "name": "Acme"})
    assert snapshot["id"] == str(identifier)


def test_state_snapshot_rejects_an_unknown_object_type() -> None:
    with pytest.raises(ForbiddenAuditPayloadError):
        state_snapshot("not_a_catalogued_type", {"id": "x"})


def test_no_allow_listed_field_is_itself_denylisted() -> None:
    # A field that is both allow-listed and denylisted would make a
    # legitimate snapshot unrecordable at validation time.
    for object_type, fields in STATE_ALLOW_LIST.items():
        for field in fields:
            lowered = field.lower()
            for fragment in FORBIDDEN_PAYLOAD_KEY_FRAGMENTS:
                assert fragment not in lowered, (
                    f"{object_type}.{field} is allow-listed but matches "
                    f"denylist fragment '{fragment}'"
                )


# --------------------------------------------------------------------------
# Section 8.3 -- the two write modes
# --------------------------------------------------------------------------


async def test_record_in_transaction_appends_without_committing() -> None:
    repository = FakeAuditEventRepository()
    session = FakeSession()
    service = AuditService(repository)

    await service.record_in_transaction(_event(action="engagement.create"))

    assert len(repository.appended) == 1
    assert repository.appended[0].action == "engagement.create"
    # The caller owns the commit; a SUCCESS event must not become durable
    # independently of the business change it describes.
    assert session.committed is False


async def test_record_out_of_band_commits_its_own_session() -> None:
    repository = FakeAuditEventRepository()
    session = FakeSession()
    service = AuditService(repository)

    await service.record_out_of_band(
        _event(result=AuditResult.DENIED, action="organization.update"), session
    )

    assert len(repository.appended) == 1
    assert session.committed is True


async def test_a_failed_audit_write_does_not_raise_and_is_logged_as_an_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Decision D-3: fail-open, loudly. A failed audit write must never
    # convert a completed operation into a 500.
    repository = FakeAuditEventRepository(fail_on_append=True)
    session = FakeSession()
    service = AuditService(repository)
    correlation_id = str(uuid4())

    with caplog.at_level(logging.ERROR, logger="app.audit"):
        await service.record_out_of_band(
            _event(result=AuditResult.DENIED, correlation_id=correlation_id), session
        )

    assert session.committed is False
    assert session.rolled_back is True

    messages = [record.getMessage() for record in caplog.records]
    assert any("AUDIT WRITE FAILED" in message for message in messages)
    # The correlation id is what makes the lost event traceable back to
    # the request in the application log.
    assert any(correlation_id in message for message in messages)


# --------------------------------------------------------------------------
# Field-level guarantees
# --------------------------------------------------------------------------


async def test_a_user_attributed_event_without_an_actor_id_is_rejected() -> None:
    service = AuditService(FakeAuditEventRepository())
    with pytest.raises(ForbiddenAuditPayloadError):
        await service.record_in_transaction(
            _event(actor_type=ActorType.USER, actor_user_id=None)
        )


async def test_an_anonymous_event_may_omit_the_actor_id() -> None:
    repository = FakeAuditEventRepository()
    service = AuditService(repository)

    await service.record_in_transaction(
        _event(
            actor_type=ActorType.ANONYMOUS,
            actor_user_id=None,
            organization_id=None,
            result=AuditResult.DENIED,
            action="auth.token_rejected",
        )
    )

    assert repository.appended[0].actor_user_id is None
    assert repository.appended[0].organization_id is None


async def test_an_overlong_reason_is_truncated_to_the_column_width() -> None:
    repository = FakeAuditEventRepository()
    service = AuditService(repository)

    await service.record_in_transaction(_event(reason="x" * 900))

    assert repository.appended[0].reason is not None
    assert len(repository.appended[0].reason) == 500


async def test_an_overlong_user_agent_is_truncated_rather_than_rejected() -> None:
    # A hostile client must not be able to prevent its own actions from
    # being audited by sending an enormous header.
    repository = FakeAuditEventRepository()
    service = AuditService(repository)

    await service.record_in_transaction(_event(user_agent="u" * 5000))

    assert repository.appended[0].user_agent is not None
    assert len(repository.appended[0].user_agent) == 256
