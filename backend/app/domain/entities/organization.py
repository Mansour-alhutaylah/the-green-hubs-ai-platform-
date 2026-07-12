"""Pure domain entity for an Organization.

Framework-independent by design, mirroring ``Document``'s shape. Unlike
``Document`` (whose ``id`` is generated client-side before persistence),
``organizations.id`` and ``organizations.created_at`` are both generated
server-side (``gen_random_uuid()`` / ``CURRENT_TIMESTAMP``), so both are
``None`` on an entity that has not yet been persisted. ``created_at`` stays
``Optional`` even after persistence: the database column itself is
nullable, and this entity must never invent a value the schema does not
guarantee.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Organization:
    id: UUID | None
    name: str
    created_at: datetime | None
