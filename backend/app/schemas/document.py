"""Pydantic response model for the Document upload endpoint.

``storage_path`` is deliberately omitted: it is an internal storage
detail with no client-facing use this sprint. A future, deliberately
designed download endpoint (e.g. returning a signed URL) is the right
place for retrieval -- not exposing the raw object key now.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: UUID
    engagement_id: UUID
    filename: str
    processing_status: str
    created_at: datetime
    updated_at: datetime
