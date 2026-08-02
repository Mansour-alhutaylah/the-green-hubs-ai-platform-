"""Direct HTTP coverage for application-wide exception handling.

The test app uses the production exception registration and CORS
middleware with an explicit, isolated settings object.  It has no
database, storage, authentication, or external-provider dependencies.
"""

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.exceptions import NotFoundError, register_exception_handlers

_ALLOWED_ORIGIN = "https://frontend.example.test"
_PRIVATE_ERROR_MESSAGE = "sensitive-internal-detail from a private database adapter"
_SAFE_ERROR_PAYLOAD = {"detail": "An unexpected error occurred. Please try again later."}


def _build_test_app() -> FastAPI:
    settings = Settings(
        _env_file=None,
        debug=False,
        backend_cors_origins=[_ALLOWED_ORIGIN],
    )
    app = FastAPI(debug=settings.debug)
    register_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/unexpected")
    async def unexpected_error() -> None:
        raise RuntimeError(_PRIVATE_ERROR_MESSAGE)

    @app.get("/controlled")
    async def controlled_error() -> None:
        raise NotFoundError("Requested resource not found")

    @app.get("/validated/{item_id}")
    async def validated_route(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    return app


@pytest.fixture
async def exception_client() -> AsyncClient:
    transport = ASGITransport(app=_build_test_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_unexpected_error_returns_sanitized_500_response(
    exception_client: AsyncClient,
) -> None:
    response = await exception_client.get("/unexpected")

    assert response.status_code == 500
    assert response.json() == _SAFE_ERROR_PAYLOAD

    body = response.text
    assert _PRIVATE_ERROR_MESSAGE not in body
    assert "RuntimeError" not in body
    assert "Traceback" not in body
    assert "test_exception_handling.py" not in body
    assert "stack frame" not in body


async def test_unexpected_error_preserves_cors_headers_for_allowed_origin(
    exception_client: AsyncClient,
) -> None:
    response = await exception_client.get(
        "/unexpected",
        headers={"Origin": _ALLOWED_ORIGIN},
    )

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == _ALLOWED_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["vary"] == "Origin"


async def test_unexpected_error_without_origin_does_not_fabricate_cors_headers(
    exception_client: AsyncClient,
) -> None:
    response = await exception_client.get("/unexpected")

    assert response.status_code == 500
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-credentials" not in response.headers


async def test_controlled_application_error_keeps_its_status_and_payload(
    exception_client: AsyncClient,
) -> None:
    response = await exception_client.get("/controlled")

    assert response.status_code == 404
    assert response.json() == {"detail": "Requested resource not found"}


async def test_request_validation_error_remains_422(
    exception_client: AsyncClient,
) -> None:
    response = await exception_client.get("/validated/not-an-integer")

    assert response.status_code == 422
    body = response.json()
    assert isinstance(body["detail"], list)
    assert body["detail"][0]["loc"] == ["path", "item_id"]
