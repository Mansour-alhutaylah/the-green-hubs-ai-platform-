"""Abstract repository interface for ``User`` profile entities.

Only ``get()`` (inherited from ``IRepository``) is exercised by this
sprint's Authentication Foundation. ``list``/``create``/``update``/
``delete`` are inherited for interface completeness -- mirroring
``IOrganizationRepository``'s unexposed ``delete()`` -- but are not called
by any service or route here; user creation/registration is explicitly
out of scope.
"""

from abc import ABC

from app.domain.entities.user import User
from app.domain.repositories.base import IRepository


class IUserRepository(IRepository[User], ABC):
    pass
