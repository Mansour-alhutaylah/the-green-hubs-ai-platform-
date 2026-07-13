"""Unit tests for ``SupabaseDocumentStorage`` -- every HTTP call is
intercepted via ``httpx.MockTransport``. No real network call, no live
Supabase Storage, no bucket required.
"""

import httpx
import pytest

from app.core.config import Settings
from app.domain.storage.document_storage import StorageError
from app.infrastructure.storage.supabase_document_storage import SupabaseDocumentStorage


def _settings(**overrides: object) -> Settings:
    defaults: dict = {
        "supabase_url": "https://example-project.supabase.co",
        "supabase_service_role_key": "test-service-role-key",
        "supabase_storage_bucket": "test-bucket",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_raises_when_supabase_url_missing() -> None:
    with pytest.raises(RuntimeError):
        SupabaseDocumentStorage(_settings(supabase_url=None))


def test_raises_when_service_role_key_missing() -> None:
    with pytest.raises(RuntimeError):
        SupabaseDocumentStorage(_settings(supabase_service_role_key=None))


def test_raises_when_bucket_missing() -> None:
    with pytest.raises(RuntimeError):
        SupabaseDocumentStorage(_settings(supabase_storage_bucket=None))


async def test_put_sends_expected_request_and_succeeds_on_2xx() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["content"] = request.content
        return httpx.Response(200)

    storage = SupabaseDocumentStorage(_settings(), transport=httpx.MockTransport(handler))

    await storage.put("organizations/org/engagements/eng/documents/doc.pdf", b"%PDF-1.4", "application/pdf")

    assert captured["method"] == "POST"
    assert captured["url"].endswith(
        "/storage/v1/object/test-bucket/organizations/org/engagements/eng/documents/doc.pdf"
    )
    assert captured["headers"]["authorization"] == "Bearer test-service-role-key"
    assert captured["headers"]["apikey"] == "test-service-role-key"
    assert captured["headers"]["content-type"] == "application/pdf"
    assert captured["content"] == b"%PDF-1.4"


async def test_put_raises_storage_error_on_non_2xx() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="bucket not found")

    storage = SupabaseDocumentStorage(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(StorageError):
        await storage.put("some/key.pdf", b"%PDF-1.4", "application/pdf")


async def test_put_raises_storage_error_on_transport_failure() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    storage = SupabaseDocumentStorage(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(StorageError):
        await storage.put("some/key.pdf", b"%PDF-1.4", "application/pdf")


async def test_delete_sends_expected_request_and_succeeds_on_2xx() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        return httpx.Response(200)

    storage = SupabaseDocumentStorage(_settings(), transport=httpx.MockTransport(handler))

    await storage.delete("organizations/org/engagements/eng/documents/doc.pdf")

    assert captured["method"] == "DELETE"
    assert captured["url"].endswith(
        "/storage/v1/object/test-bucket/organizations/org/engagements/eng/documents/doc.pdf"
    )


async def test_delete_raises_storage_error_on_non_2xx() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    storage = SupabaseDocumentStorage(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(StorageError):
        await storage.delete("some/key.pdf")


async def test_delete_raises_storage_error_on_transport_failure() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    storage = SupabaseDocumentStorage(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(StorageError):
        await storage.delete("some/key.pdf")
