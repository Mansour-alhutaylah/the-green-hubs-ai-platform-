"""Pure domain entity for an Engagement.

Framework-independent, mirroring ``Organization``'s shape. ``id`` and
``created_at`` are server-generated, so both are ``None`` before
persistence. ``organization_id`` and ``status`` are typed ``Optional`` to
honestly represent the ``engagements`` table's actual nullable columns --
a row created outside the approved API path (or a pre-existing row) could
have either as ``NULL``, even though every row created through
``EngagementService`` always has both populated (``status`` defaulting to
``"planning"``). ``title`` stays a required ``str``: that column is
``NOT NULL``.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Engagement:
    id: UUID | None
    organization_id: UUID | None
    title: str
    status: str | None
    created_at: datetime | None
