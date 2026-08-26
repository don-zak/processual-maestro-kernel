from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from processual_api.auth import mfa_router, registration_router, session_router
from processual_api.auth.mfa_runtime import MfaRuntimeUnavailableError
from processual_api.auth.rate_limit import AuthRateLimitDecision, AuthRateLimitUnavailableError
from processual_api.auth.registration_runtime import RegistrationRuntimeUnavailableError
from processual_api.auth.session_runtime import SessionRuntimeUnavailableError


class _UnavailableLimiter:
    async def consume(self, **kwargs: object) -> AuthRateLimitDecision:
        raise AuthRateLimitUnavailableError("redis authority unavailable")


class _DeniedLimiter:
    async def consume(self, **kwargs: object) -> AuthRateLimitDecision:
        return AuthRateLimitDecision(allowed=False, retry_after_seconds=17, remaining=0)


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/auth/test",
            "headers": [],
            "client": ("198.51.100.10", 12345),
            "server": ("testserver", 443),
            "scheme": "https",
            "query_string": b"",
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("module", "builder_name", "dependency", "exc_type", "detail"),
    [
        (
            registration_router,
            "build_registration_runtime",
            registration_router.get_registration_runtime,
            RegistrationRuntimeUnavailableError,
            registration_router.GENERIC_UNAVAILABLE,
        ),
        (
            session_router,
            "build_session_runtime",
            session_router.get_session_runtime,
            SessionRuntimeUnavailableError,
            session_router.GENERIC_UNAVAILABLE,
        ),
        (
            mfa_router,
            "build_mfa_runtime",
            mfa_router.get_mfa_runtime,
            MfaRuntimeUnavailableError,
            mfa_router.GENERIC_UNAVAILABLE,
        ),
    ],
)
async def test_auth_runtime_authority_unavailable_maps_to_503(
    monkeypatch: pytest.MonkeyPatch,
    module: object,
    builder_name: str,
    dependency: object,
    exc_type: type[RuntimeError],
    detail: str,
) -> None:
    async def _broken_builder() -> object:
        raise exc_type("authority unavailable")

    monkeypatch.setattr(module, builder_name, _broken_builder)

    with pytest.raises(HTTPException) as exc_info:
        await dependency()  # type: ignore[operator]

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == detail


@pytest.mark.asyncio
async def test_session_rate_limit_authority_failure_is_503() -> None:
    runtime = SimpleNamespace(
        rate_limiter=_UnavailableLimiter(),
        proxy_policy=SimpleNamespace(networks=()),
    )

    with pytest.raises(HTTPException) as exc_info:
        await session_router._consume_rate_limit(
            request=_request(),
            runtime=runtime,
            action="login",
            rules=session_router.LOGIN_RULES,
            subjects={"ip": "198.51.100.10", "email": "person@example.com"},
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == session_router.GENERIC_UNAVAILABLE


@pytest.mark.asyncio
async def test_session_rate_limit_rejection_is_429_with_retry_after() -> None:
    runtime = SimpleNamespace(
        rate_limiter=_DeniedLimiter(),
        proxy_policy=SimpleNamespace(networks=()),
    )

    with pytest.raises(HTTPException) as exc_info:
        await session_router._consume_rate_limit(
            request=_request(),
            runtime=runtime,
            action="login",
            rules=session_router.LOGIN_RULES,
            subjects={"ip": "198.51.100.10", "email": "person@example.com"},
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers == {"Retry-After": "17"}


@pytest.mark.asyncio
async def test_mfa_rate_limit_authority_failure_is_503() -> None:
    runtime = SimpleNamespace(
        rate_limiter=_UnavailableLimiter(),
        proxy_policy=SimpleNamespace(networks=()),
    )

    with pytest.raises(HTTPException) as exc_info:
        await mfa_router._limit_verification(
            _request(),
            runtime,
            user_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == mfa_router.GENERIC_UNAVAILABLE
