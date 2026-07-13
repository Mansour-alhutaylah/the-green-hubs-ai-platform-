"""Pure domain entity for a Document's extracted-text child record.

Framework-independent, mirroring ``Document``'s shape. ``id`` and
``created_at`` are server-generated, so both are ``None`` before
persistence. ``document_id``/``extracted_content`` are typed ``Optional``
to honestly represent the ``extracted_text`` table's actual nullable
columns (unchanged by Sprint 3.5's migration) -- even though this
application always supplies both when creating a row (enforced by
``DocumentProcessingService``, never by this entity's typing).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class ExtractedText:
    id: UUID | None
    document_id: UUID | None
    extracted_content: str | None
    created_at: datetime | None
