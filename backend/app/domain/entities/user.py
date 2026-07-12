"""Pure domain entity for a User profile.

Framework-independent, mirroring ``Organization``'s shape. Under the
approved shared-primary-key identity design (``public.users.id ==
auth.users.id``), ``id`` is always the corresponding Supabase Auth user's
id, supplied by the caller -- never server-generated -- so, unlike
``Organization``/``Engagement``, ``id`` is not ``Optional`` here: this
entity only ever represents an already-identified profile (this sprint
never constructs one pre-persistence). ``created_at`` stays ``Optional``
for the same reason as ``Organization``'s: the column is nullable and this
entity must never invent a value the schema doesn't guarantee.
``organization_id``/``role`` are ``Optional`` because those columns are
nullable.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class User:
    id: UUID
    organization_id: UUID | None
    full_name: str
    email: str
    role: str | None
    created_at: datetime | None
