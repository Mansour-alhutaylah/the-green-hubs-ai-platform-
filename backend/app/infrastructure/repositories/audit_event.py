"""Concrete async repository for ``AuditEvent``.

Phase 1A Slice 3. Implements ``IAuditEventRepository`` directly and, like
that interface, does **not** inherit ``IRepository`` -- so this class has
no ``update`` and no ``delete`` to call. That absence is layer 1 of the
append-only scheme (plan section 8.2) and is asserted by a static test
rather than left to review.

``append`` stages the row and deliberately does not commit. Both audit
write modes need that: ``record_in_transaction`` requires the event to
ride the business transaction's commit (so a rolled-back operation cannot
leave a "succeeded" event behind), and ``record_out_of_band`` owns its own
session and commits there. Committing here would break the first mode.

The tenant predicate for reads lives in the SQL ``WHERE`` clause, not in a
post-fetch comparison, matching ``SQLAlchemyEngagementRepository``'s
scoped reads. Rows with a null ``organization_id`` -- pre-tenant failures
-- match no organization and are therefore invisible to every
tenant-scoped read, which is intended.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.audit_event import ActorType, AuditEvent, AuditResult
from app.domain.repositories.audit_event import IAuditEventRepository
from app.infrastructure.db.models.audit_event import AuditEventModel


def _to_domain(model: AuditEventModel) -> AuditEvent:
    return AuditEvent(
        id=model.id,
        recorded_seq=model.recorded_seq,
        event_schema_version=model.event_schema_version,
        organization_id=model.organization_id,
        actor_user_id=model.actor_user_id,
        actor_type=ActorType(model.actor_type),
        action=model.action,
        object_type=model.object_type,
        object_id=model.object_id,
        result=AuditResult(model.result),
        previous_state=model.previous_state,
        new_state=model.new_state,
        reason=model.reason,
        correlation_id=model.correlation_id,
        occurred_at=model.occurred_at,
        request_method=model.request_method,
        request_path=model.request_path,
        client_ip=model.client_ip,
        user_agent=model.user_agent,
    )


class SQLAlchemyAuditEventRepository(IAuditEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, event: AuditEvent) -> None:
        model = AuditEventModel(
            organization_id=event.organization_id,
            actor_user_id=event.actor_user_id,
            actor_type=event.actor_type.value,
            action=event.action,
            object_type=event.object_type,
            object_id=event.object_id,
            result=event.result.value,
            previous_state=event.previous_state,
            new_state=event.new_state,
            reason=event.reason,
            correlation_id=event.correlation_id,
            request_method=event.request_method,
            request_path=event.request_path,
            client_ip=event.client_ip,
            user_agent=event.user_agent,
            event_schema_version=event.event_schema_version,
        )
        self._session.add(model)
        # Deliberately no commit and no flush: the caller owns the
        # transaction boundary. See the module docstring.

    async def list_for_organization(
        self,
        *,
        organization_id: UUID,
        limit: int,
        offset: int,
    ) -> list[AuditEvent]:
        # `recorded_seq` breaks ties on identical timestamps so that
        # pagination is stable; `occurred_at` alone is not a total order.
        statement = (
            select(AuditEventModel)
            .where(AuditEventModel.organization_id == organization_id)
            .order_by(
                AuditEventModel.occurred_at.desc(),
                AuditEventModel.recorded_seq.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(statement)
        return [_to_domain(model) for model in result.scalars().all()]

    async def count_for_organization(self, *, organization_id: UUID) -> int:
        statement = (
            select(func.count())
            .select_from(AuditEventModel)
            .where(AuditEventModel.organization_id == organization_id)
        )
        result = await self._session.execute(statement)
        return int(result.scalar_one())
