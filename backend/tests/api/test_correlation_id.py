"""HTTP evidence for correlation propagation, trusted context, and isolation."""

import asyncio
import datetime
import logging
import uuid
from typing import Sequence

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient

from app.api.deps import (
    get_current_auth_identity,
    get_current_user,
    get_user_repository,
)
from app.core.config import Settings
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    register_exception_handlers,
)
from app.core.logging import install_request_context_logging
from app.core.request_context import (
    CORRELATION_HEADER_NAME,
    RequestContextMiddleware,
    get_request_context,
)
from app.domain.entities.user import User
from app.domain.repositories.user import IUserRepository

_ALLOWED_ORIGIN = "https://frontend.example.test"
_PRIVATE_ERROR = "private adapter failure that must remain server-side"
_USER_ONE_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
_USER_TWO_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
_ORG_ONE_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
_CORRELATION_ONE = "33333333-3333-4333-8333-333333333333"
_CORRELATION_TWO = "44444444-4444-4444-8444-444444444444"


class FakeUserRepository(IUserRepository):
    def __init__(self, users: Sequence[User]) -> None:
        self._users = {user.id: user for user in users}

    async def get_by_authenticated_id(self, user_id: uuid.UUID) -> User | None:
        return self._users.get(user_id)

    async def create(self, entity: User) -> User:
        raise NotImplementedError

    async def update(self, entity: User) -> User:
        raise NotImplementedError

    async def delete(self, entity: User) -> None:
        raise NotImplementedError


def _user(user_id: uuid.UUID, organization_id: uuid.UUID | None) -> User:
    return User(
        id=user_id,
        organization_id=organization_id,
        full_name="Trusted User",
        email="trusted@example.test",
        role="member",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )


def _build_test_app() -> FastAPI:
    settings = Settings(
        _env_file=None,
        debug=False,
        backend_cors_origins=[_ALLOWED_ORIGIN],
    )
    install_request_context_logging()
    app = FastAPI(debug=settings.debug)
    register_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[CORRELATION_HEADER_NAME],
    )
    app.add_middleware(RequestContextMiddleware)

    users = FakeUserRepository(
        [_user(_USER_ONE_ID, _ORG_ONE_ID), _user(_USER_TWO_ID, None)]
    )

    def trusted_identity(request: Request) -> uuid.UUID:
        return (
            _USER_TWO_ID if request.path_params.get("slot") == "two" else _USER_ONE_ID
        )

    app.dependency_overrides[get_current_auth_identity] = trusted_identity
    app.dependency_overrides[get_user_repository] = lambda: users

    @app.get("/success")
    async def success(request: Request) -> dict[str, str | None]:
        context = get_request_context()
        assert context is not None
        assert request.state.request_context == context
        logging.getLogger("app.test").info("safe application event")
        return {
            "correlation_id": context.correlation_id,
            "user_id": None,
            "organization_id": None,
        }

    @app.get("/unauthorized")
    async def unauthorized() -> None:
        raise AuthenticationError("Invalid authentication credentials")

    @app.get("/forbidden")
    async def forbidden() -> None:
        raise AuthorizationError("Forbidden")

    @app.get("/controlled")
    async def controlled() -> None:
        raise NotFoundError("Requested resource not found")

    @app.get("/unexpected")
    async def unexpected() -> None:
        raise RuntimeError(_PRIVATE_ERROR)

    @app.get("/validated/{item_id}")
    async def validated(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    @app.get("/authenticated/{slot}")
    async def authenticated(
        request: Request,
        slot: str,
        current_user: User = Depends(get_current_user),
    ) -> dict[str, str | None]:
        context = get_request_context()
        assert context is not None
        assert request.state.request_context == context
        assert current_user.id == context.user_id
        return {
            "correlation_id": context.correlation_id,
            "user_id": str(context.user_id),
            "organization_id": (
                str(context.organization_id)
                if context.organization_id is not None
                else None
            ),
        }

    overlap_count = 0
    overlap_lock = asyncio.Lock()
    both_requests_ready = asyncio.Event()

    @app.get("/overlap/{slot}")
    async def overlap(
        request: Request,
        slot: str,
        current_user: User = Depends(get_current_user),
    ) -> dict[str, str | None]:
        nonlocal overlap_count
        context_before_wait = get_request_context()
        assert context_before_wait is not None
        async with overlap_lock:
            overlap_count += 1
            if overlap_count == 2:
                both_requests_ready.set()
        await both_requests_ready.wait()
        context_after_wait = get_request_context()
        assert context_after_wait == context_before_wait
        assert request.state.request_context == context_after_wait
        logging.getLogger("app.overlap").info("overlap slot=%s", slot)
        return {
            "correlation_id": context_after_wait.correlation_id,
            "user_id": str(current_user.id),
            "organization_id": (
                str(context_after_wait.organization_id)
                if context_after_wait.organization_id is not None
                else None
            ),
        }

    return app


@pytest.fixture
async def correlation_client() -> AsyncClient:
    transport = ASGITransport(app=_build_test_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _assert_uuid(value: str) -> None:
    assert str(uuid.UUID(value)) == value


def _completion_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if record.name == "app.request"
        and record.message.startswith("HTTP request completed")
    ]


async def test_generates_header_and_uses_same_context(
    correlation_client: AsyncClient,
) -> None:
    response = await correlation_client.get("/success")

    assert response.status_code == 200
    correlation_id = response.headers[CORRELATION_HEADER_NAME]
    _assert_uuid(correlation_id)
    assert response.json()["correlation_id"] == correlation_id
    assert get_request_context() is None


async def test_preserves_and_normalizes_valid_inbound_id_in_context_and_logs(
    correlation_client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app")
    supplied = _CORRELATION_ONE.upper()

    response = await correlation_client.get(
        "/success", headers={CORRELATION_HEADER_NAME: supplied}
    )

    assert response.headers[CORRELATION_HEADER_NAME] == _CORRELATION_ONE
    assert response.json()["correlation_id"] == _CORRELATION_ONE
    application_record = next(
        record for record in caplog.records if record.name == "app.test"
    )
    completion_record = _completion_records(caplog)[-1]
    assert application_record.correlation_id == _CORRELATION_ONE
    assert completion_record.correlation_id == _CORRELATION_ONE
    assert completion_record.user_id == "-"
    assert completion_record.organization_id == "-"


@pytest.mark.parametrize(
    "unsafe_value",
    [
        "not-a-uuid",
        "x" * 256,
        "33333333 3333-4333-8333-333333333333",
        "33333333-3333-4333-8333-INJECTED_LOG_DATA",
    ],
)
async def test_replaces_invalid_values_without_reflection_or_logging(
    correlation_client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
    unsafe_value: str,
) -> None:
    caplog.set_level(logging.INFO, logger="app")

    response = await correlation_client.get(
        "/success", headers={CORRELATION_HEADER_NAME: unsafe_value}
    )

    generated = response.headers[CORRELATION_HEADER_NAME]
    _assert_uuid(generated)
    assert generated != unsafe_value
    assert unsafe_value not in response.text
    assert unsafe_value not in "\n".join(
        record.getMessage() for record in caplog.records
    )


@pytest.mark.parametrize(
    ("path", "expected_status"),
    [
        ("/success", 200),
        ("/unauthorized", 401),
        ("/forbidden", 403),
        ("/missing", 404),
        ("/validated/not-an-integer", 422),
        ("/controlled", 404),
        ("/unexpected", 500),
    ],
)
async def test_correlation_header_covers_success_and_error_responses(
    correlation_client: AsyncClient, path: str, expected_status: int
) -> None:
    response = await correlation_client.get(path)

    assert response.status_code == expected_status
    _assert_uuid(response.headers[CORRELATION_HEADER_NAME])


async def test_unexpected_error_is_sanitized_and_uses_one_id_in_error_and_completion_logs(
    correlation_client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app")

    response = await correlation_client.get(
        "/unexpected", headers={CORRELATION_HEADER_NAME: _CORRELATION_ONE}
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "An unexpected error occurred. Please try again later."
    }
    assert _PRIVATE_ERROR not in response.text
    error_record = next(
        record for record in caplog.records if record.message == "Unhandled exception"
    )
    completion_record = _completion_records(caplog)[-1]
    assert error_record.correlation_id == _CORRELATION_ONE
    assert completion_record.correlation_id == _CORRELATION_ONE
    assert response.headers[CORRELATION_HEADER_NAME] == _CORRELATION_ONE


async def test_cors_exposes_correlation_header_and_preserves_error_cors(
    correlation_client: AsyncClient,
) -> None:
    response = await correlation_client.get(
        "/unexpected",
        headers={"Origin": _ALLOWED_ORIGIN, CORRELATION_HEADER_NAME: _CORRELATION_ONE},
    )

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == _ALLOWED_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    exposed = {
        value.strip().lower()
        for value in response.headers["access-control-expose-headers"].split(",")
    }
    assert CORRELATION_HEADER_NAME.lower() in exposed
    assert response.headers[CORRELATION_HEADER_NAME] == _CORRELATION_ONE


async def test_request_without_origin_has_correlation_but_no_false_cors(
    correlation_client: AsyncClient,
) -> None:
    response = await correlation_client.get("/success")

    assert CORRELATION_HEADER_NAME in response.headers
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-credentials" not in response.headers


@pytest.mark.parametrize(
    ("slot", "expected_user", "expected_organization"),
    [
        ("one", _USER_ONE_ID, _ORG_ONE_ID),
        ("two", _USER_TWO_ID, None),
    ],
)
async def test_trusted_profile_enriches_context_and_client_headers_cannot_spoof_it(
    correlation_client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
    slot: str,
    expected_user: uuid.UUID,
    expected_organization: uuid.UUID | None,
) -> None:
    caplog.set_level(logging.INFO, logger="app")
    spoofed_user = uuid.uuid4()
    spoofed_organization = uuid.uuid4()

    response = await correlation_client.get(
        f"/authenticated/{slot}",
        headers={
            "X-User-ID": str(spoofed_user),
            "X-Organization-ID": str(spoofed_organization),
        },
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == str(expected_user)
    expected_org_text = (
        str(expected_organization) if expected_organization is not None else None
    )
    assert response.json()["organization_id"] == expected_org_text
    completion_record = _completion_records(caplog)[-1]
    assert completion_record.user_id == str(expected_user)
    assert completion_record.organization_id == (expected_org_text or "-")
    assert str(spoofed_user) not in completion_record.getMessage()
    assert str(spoofed_organization) not in completion_record.getMessage()


async def test_completion_log_excludes_query_credentials_cookies_and_bodies(
    correlation_client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app")
    secret_query = "query-secret-value"
    secret_token = "bearer-secret-value"
    secret_cookie = "cookie-secret-value"

    response = await correlation_client.get(
        f"/success?secret={secret_query}",
        headers={
            "Authorization": f"Bearer {secret_token}",
            "Cookie": f"session={secret_cookie}",
        },
    )

    assert response.status_code == 200
    completion_message = _completion_records(caplog)[-1].getMessage()
    assert "path=/success" in completion_message
    assert "?" not in completion_message
    assert secret_query not in completion_message
    assert secret_token not in completion_message
    assert secret_cookie not in completion_message


async def test_concurrent_requests_keep_context_identity_and_logs_isolated(
    correlation_client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app")

    response_one, response_two = await asyncio.gather(
        correlation_client.get(
            "/overlap/one", headers={CORRELATION_HEADER_NAME: _CORRELATION_ONE}
        ),
        correlation_client.get(
            "/overlap/two", headers={CORRELATION_HEADER_NAME: _CORRELATION_TWO}
        ),
    )

    assert response_one.json() == {
        "correlation_id": _CORRELATION_ONE,
        "user_id": str(_USER_ONE_ID),
        "organization_id": str(_ORG_ONE_ID),
    }
    assert response_two.json() == {
        "correlation_id": _CORRELATION_TWO,
        "user_id": str(_USER_TWO_ID),
        "organization_id": None,
    }
    overlap_records = [
        record for record in caplog.records if record.name == "app.overlap"
    ]
    records_by_correlation = {
        record.correlation_id: record for record in overlap_records
    }
    assert records_by_correlation[_CORRELATION_ONE].user_id == str(_USER_ONE_ID)
    assert records_by_correlation[_CORRELATION_ONE].organization_id == str(_ORG_ONE_ID)
    assert records_by_correlation[_CORRELATION_TWO].user_id == str(_USER_TWO_ID)
    assert records_by_correlation[_CORRELATION_TWO].organization_id == "-"
    assert get_request_context() is None


async def test_duplicate_inbound_headers_are_replaced_and_response_is_not_duplicated(
    correlation_client: AsyncClient,
) -> None:
    response = await correlation_client.get(
        "/success",
        headers=[
            (CORRELATION_HEADER_NAME, _CORRELATION_ONE),
            (CORRELATION_HEADER_NAME, _CORRELATION_TWO),
        ],
    )

    returned_values = response.headers.get_list(CORRELATION_HEADER_NAME)
    assert len(returned_values) == 1
    _assert_uuid(returned_values[0])
    assert returned_values[0] not in {_CORRELATION_ONE, _CORRELATION_TWO}
