"""Abstract interface for document object storage.

Framework- and provider-independent: no Supabase SDK, no HTTP client
import. Scoped to exactly what Document Upload and Document Processing
need -- no listing, signed-URL, or public-URL support.

``DocumentUploadService``/``DocumentProcessingService`` depend on this
interface only, never on a concrete storage implementation, mirroring
how they depend on ``IEngagementRepository`` rather than a SQLAlchemy
class.

``get()`` (Sprint 3.5) raises one of three specific subclasses so the
caller can distinguish object-missing from provider-unavailable from a
provider auth/configuration failure -- ``DocumentProcessingService``
maps these to ``NotFoundError``/``PersistenceError`` without ever
exposing the provider's raw response to a client.
"""

from abc import ABC, abstractmethod


class StorageError(Exception):
    """Raised when a storage operation fails.

    Wraps the provider's underlying error without leaking its internals --
    callers (the service layer) map this to a generic, non-leaking
    application error.
    """


class StorageObjectNotFoundError(StorageError):
    """The requested object does not exist in the storage provider."""


class StorageUnavailableError(StorageError):
    """The storage provider could not be reached (network/connection
    failure, timeout, DNS failure, etc.)."""


class StorageConfigurationError(StorageError):
    """The storage provider rejected the request due to authentication or
    configuration (e.g. an invalid/expired service-role key)."""


class IDocumentStorage(ABC):
    @abstractmethod
    async def put(self, object_key: str, content: bytes, content_type: str) -> None: ...

    @abstractmethod
    async def get(self, object_key: str) -> bytes: ...

    @abstractmethod
    async def delete(self, object_key: str) -> None: ...
