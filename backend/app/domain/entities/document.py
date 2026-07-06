"""Pure domain entity for a sustainability source document.

Framework-independent by design: no SQLAlchemy, no Pydantic, no ORM
relationships. Mirrors the shape of Hemaya's ``Policy`` model
(``backend/models.py``) as design inspiration only -- renamed to ``Document``
because this platform's source artifacts are sustainability disclosures in
general, not compliance "policies", and trimmed to only the fields needed
before analysis/versioning/reporting concepts exist in this codebase.
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
