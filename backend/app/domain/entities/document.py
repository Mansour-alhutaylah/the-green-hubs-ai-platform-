"""Pure domain entity for a sustainability source document.

Framework-independent by design: no SQLAlchemy, no Pydantic, no ORM
relationships. Mirrors the shape of Hemaya's ``Policy`` model
(``backend/models.py``) as design inspiration only -- renamed to ``Document``
because this platform's source artifacts are sustainability disclosures in
general, not compliance "policies", and trimmed to only the fields needed
before analysis/versioning/reporting concepts exist in this codebase.

``updated_at`` added in Sprint 3.4 (Document Upload Foundation): the
``documents`` table has always had this column, but nothing needed it
surfaced in the domain entity until the upload response contract required
it. Both timestamp fields stay non-Optional, matching every column on this
table being ``NOT NULL`` -- unlike ``Organization``/``Engagement``/``User``,
Document has no nullable-timestamp case to represent.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Document:
    id: UUID
    filename: str
    storage_path: str
    processing_status: str
    engagement_id: UUID
    created_at: datetime
    updated_at: datetime
