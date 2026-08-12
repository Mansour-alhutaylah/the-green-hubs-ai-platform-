"""Concrete async repository for the ``User`` profile aggregate.

Implements ``IUserRepository`` directly, mirroring
``SQLAlchemyOrganizationRepository``: ``_to_domain`` maps the ORM model
(imported aliased since it shares the name ``User`` with the domain
entity) to the domain ``User``. ``create``/``update``/``delete`` exist only
for ``IRepository`` interface completeness -- the authentication flow only
ever calls ``get_by_authenticated_id()``; user creation/registration is out
of scope.

MVP Slice 3 closure: ``list()`` has been **removed**, not merely left
unused. It returned every user in every organization along with their
names and email addresses -- a global tenant bypass available to any
future caller. No user-management route or service exists (see
``app/domain/security/permissions.py``), and a future one must add an
explicitly tenant-scoped ``list_for_organization`` following
``IEngagementRepository``'s convention.

The generic ``get`` was renamed ``get_by_authenticated_id`` for the same
reason: it is the authentication bootstrap, not general-purpose access,
and the name now says so. See ``IUserRepository`` for the full statement
of that exception and why it is safe.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domain.entities.user import User
from app.domain.repositories.user import IUserRepository
from app.infrastructure.db.models.user import User as UserModel


def _to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        organization_id=model.organization_id,
        full_name=model.full_name,
        email=model.email,
        role=model.role,
        created_at=model.created_at,
    )


class SQLAlchemyUserRepository(IUserRepository):
    """Async, PostgreSQL-backed implementation of ``IUserRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_authenticated_id(self, user_id: UUID) -> User | None:
        """The authentication bootstrap -- see ``IUserRepository``.

        ``user_id`` is the ``sub`` of an already signature-verified JWT,
        so this can only ever return the caller's own profile. It is the
        one read in the codebase with no organization scope, because it
        is what produces the organization scope."""

        model = await self._session.get(UserModel, user_id)
        return _to_domain(model) if model is not None else None

    async def create(self, entity: User) -> User:
        model = UserModel(
            id=entity.id,
            organization_id=entity.organization_id,
            full_name=entity.full_name,
            email=entity.email,
            role=entity.role,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def update(self, entity: User) -> User:
        model = await self._session.get(UserModel, entity.id)
        if model is None:
            raise NotFoundError(f"User {entity.id} not found")
        model.organization_id = entity.organization_id
        model.full_name = entity.full_name
        model.email = entity.email
        model.role = entity.role
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def delete(self, entity: User) -> None:
        model = await self._session.get(UserModel, entity.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.commit()
