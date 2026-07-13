"""Concrete ``IDocumentStorage`` backed by Supabase Storage's REST API.

Uses a narrow ``httpx.AsyncClient`` call against Supabase Storage's object
endpoints directly -- not the ``supabase-py`` SDK, which would pull in a
much larger dependency tree (postgrest-py, gotrue, realtime-py, storage3)
for functionality this sprint needs exactly three operations from.
``httpx`` was already a project dependency (previously dev-only, for the
ASGI test client); this makes it a runtime dependency too.

The bucket is provisioned as an explicit infrastructure setup step, outside
this codebase -- this class never creates it, never alters its policies,
and never makes it public.

``get()`` (Sprint 3.5) distinguishes three failure causes: a 404 response
maps to ``StorageObjectNotFoundError``, a transport-level failure (DNS,
connection, timeout) maps to ``StorageUnavailableError``, and a 401/403
response maps to ``StorageConfigurationError`` -- callers
(``DocumentProcessingService``) map these to safe application errors
without ever exposing the provider's raw response.

Authenticates with the service-role key (elevated access, bypasses RLS --
mirroring how this backend's own Postgres connection already bypasses RLS
via the ``postgres`` role, per the Sprint 3.3 RLS findings). This key is
never exposed to the frontend or included in any response.
"""

import httpx

from app.core.config import Settings
from app.domain.storage.document_storage import (
    IDocumentStorage,
    StorageConfigurationError,
    StorageError,
    StorageObjectNotFoundError,
    StorageUnavailableError,
)

_REQUEST_TIMEOUT_SECONDS = 30.0


class SupabaseDocumentStorage(IDocumentStorage):
    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        """``transport`` is a unit-test seam only (e.g. ``httpx.MockTransport``)
        -- production code never passes it, so httpx uses its real transport.
        """
        if not settings.supabase_url:
            raise RuntimeError("SUPABASE_URL must be configured to use Supabase Storage")
        if not settings.supabase_service_role_key:
            raise RuntimeError(
                "SUPABASE_SERVICE_ROLE_KEY must be configured to use Supabase Storage"
            )
        if not settings.supabase_storage_bucket:
            raise RuntimeError(
                "SUPABASE_STORAGE_BUCKET must be configured to use Supabase Storage"
            )
        self._base_url = settings.supabase_url.rstrip("/")
        self._bucket = settings.supabase_storage_bucket
        self._headers = {
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
        }
        self._transport = transport

    def _object_url(self, object_key: str) -> str:
        return f"{self._base_url}/storage/v1/object/{self._bucket}/{object_key}"

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS, transport=self._transport)

    async def put(self, object_key: str, content: bytes, content_type: str) -> None:
        try:
            async with self._client() as client:
                response = await client.post(
                    self._object_url(object_key),
                    content=content,
                    headers={**self._headers, "Content-Type": content_type},
                )
        except httpx.HTTPError as exc:
            raise StorageError("Unable to reach the storage provider") from exc
        if response.status_code >= 400:
            raise StorageError(f"Storage upload failed with status {response.status_code}")

    async def delete(self, object_key: str) -> None:
        try:
            async with self._client() as client:
                response = await client.delete(self._object_url(object_key), headers=self._headers)
        except httpx.HTTPError as exc:
            raise StorageError("Unable to reach the storage provider") from exc
        if response.status_code >= 400:
            raise StorageError(f"Storage delete failed with status {response.status_code}")

    async def get(self, object_key: str) -> bytes:
        try:
            async with self._client() as client:
                response = await client.get(self._object_url(object_key), headers=self._headers)
        except httpx.HTTPError as exc:
            raise StorageUnavailableError("Unable to reach the storage provider") from exc
        if response.status_code == 404:
            raise StorageObjectNotFoundError(f"Object not found: {object_key}")
        if response.status_code in (401, 403):
            raise StorageConfigurationError("Storage provider rejected the request")
        if response.status_code >= 400:
            raise StorageError(f"Storage retrieval failed with status {response.status_code}")
        return response.content
