"""Concrete ``IDocumentStorage`` backed by Supabase Storage's REST API.

Uses a narrow ``httpx.AsyncClient`` call against Supabase Storage's object
endpoints directly -- not the ``supabase-py`` SDK, which would pull in a
much larger dependency tree (postgrest-py, gotrue, realtime-py, storage3)
for functionality this sprint needs exactly two operations from. ``httpx``
was already a project dependency (previously dev-only, for the ASGI test
client); this makes it a runtime dependency too.

The bucket is provisioned as an explicit infrastructure setup step, outside
this codebase -- this class never creates it, never alters its policies,
and never makes it public. A missing/inaccessible bucket, an unreachable
Supabase instance, or any non-2xx response surfaces uniformly as
``StorageError``; the caller (``DocumentUploadService``) maps that to a
generic application error without leaking provider details to the client.

Authenticates with the service-role key (elevated access, bypasses RLS --
mirroring how this backend's own Postgres connection already bypasses RLS
via the ``postgres`` role, per the Sprint 3.3 RLS findings). This key is
never exposed to the frontend or included in any response.
"""

import httpx

from app.core.config import Settings
from app.domain.storage.document_storage import IDocumentStorage, StorageError

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
