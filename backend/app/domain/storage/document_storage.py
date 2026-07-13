"""Abstract interface for document object storage.

Framework- and provider-independent: no Supabase SDK, no HTTP client
import. Scoped to exactly what Document Upload Foundation needs -- no
download, listing, signed-URL, or public-URL support this sprint.

``DocumentUploadService`` depends on this interface only, never on a
concrete storage implementation, mirroring how it depends on
``IEngagementRepository`` rather than a SQLAlchemy class.
"""

from abc import ABC, abstractmethod


class StorageError(Exception):
    """Raised when a storage operation fails.

    Wraps the provider's underlying error without leaking its internals --
    callers (the service layer) map this to a generic, non-leaking
    application error.
    """


class IDocumentStorage(ABC):
    @abstractmethod
    async def put(self, object_key: str, content: bytes, content_type: str) -> None: ...

    @abstractmethod
    async def delete(self, object_key: str) -> None: ...
