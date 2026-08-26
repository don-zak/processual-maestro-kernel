from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from processual_api.auth import mfa_router, registration_router, session_router
from processual_api.auth.mfa_runtime import MfaRuntimeUnavailableError
from processual_api.auth.rate_limit import (
    AuthRateLimitDecision,
    AuthRateLimitUnavailableError,
    TrustedProxyPolicy,
)
from processual_api.auth.registration_contracts import (
    IndividualRegistrationRequestContract,
    RegistrationMode,
)
from processual_api.auth.registration_runtime import RegistrationRuntimeUnavailableError
from processual_api.auth.session_runtime import SessionRuntimeUnavailableError


class UnavailableLimiter:
    async def consume(self, **kwargs: object) -> AuthRateLimitDecision:
        raise AuthRateLimitUnavailableError("redis authority unavailable")


class DeniedLimiter:
    async def consume(self, **kwargs: object) -> AuthRateLimitDecision:
        return AuthRateLimitDecision(
            allowed=False,
            retry_after_seconds=17,
            remaining=0,
        )


def request_for(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [],
            "client": ("198.51.100.10", 12345),
            "server": ("testserver", 443),
            "scheme": "https",
            "query_string": b"",
        }
    )


@pytest.mark.asyncio
async def test_registration_runtime_unavailable_maps_to_generic_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def broken_builder() -> object:
        raise RegistrationRuntimeUnavailableError("authority unavailable")

    monkeypatch.setattr(registration_router, "build_registration_runtime", broken_builder)

    with pytest.raises(HTTPException) as exc_info:
        await registration_router.get_registration_runtime()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == registration_router.GENERIC_UNAVAILABLE


@pytest.mark.asyncio
async def test_session_runtime_unavailable_maps_to_generic_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def broken_builder() -> object:
        raise SessionRuntimeUnavailableError("authority unavailable")

    monkeypatch.setattr(session_router, "build_session_runtime", broken_builder)

    with pytest.raises(HTTPException) as exc_info:
        await session_router.get_session_runtime()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == session_router.GENERIC_UNAVAILABLE


@pytest.mark.asyncio
async def test_mfa_runtime_unavailable_maps_to_generic_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def broken_builder() -> object:
        raise MfaRuntimeUnavailableError("authority unavailable")

    monkeypatch.setattr(mfa_router, "build_mfa_runtime", broken_builder)

    with pytest.raises(HTTPException) as exc_info:
        await mfa_router.get_mfa_runtime()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == mfa_router.GENERIC_UNAVAILABLE


@pytest.mark.asyncio
async def test_registration_rate_limit_authority_failure_is_503() -> None:
    runtime = SimpleNamespace(
        rate_limiter=UnavailableLimiter(),
        proxy_policy=TrustedProxyPolicy(),
        minimum_response_seconds=0.0,
        service=object(),
    )
    payload = IndividualRegistrationRequestContract(
        email="person@example.com",
        full_name="Test Person",
        password="correct-horse-battery-staple",
        accepted_terms_version="v1",
    )

    response = await registration_router._register(
        request=request_for("/auth/register"),
        payload=payload,
        mode=RegistrationMode.INDIVIDUAL,
        rules=registration_router.REGISTRATION_RULES,
        runtime=runtime,
    )

    assert response.status_code == 503
    assert json.loads(response.body) == {"detail": registration_router.GENERIC_UNAVAILABLE}


@pytest.mark.asyncio
async def test_session_rate_limit_authority_failure_is_503() -> None:
    runtime = SimpleNamespace(
        rate_limiter=UnavailableLimiter(),
        proxy_policy=TrustedProxyPolicy(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await session_router._consume_rate_limit(
            request=request_for("/auth/login"),
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
        rate_limiter=DeniedLimiter(),
        proxy_policy=TrustedProxyPolicy(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await session_router._consume_rate_limit(
            request=request_for("/auth/login"),
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
        rate_limiter=UnavailableLimiter(),
        proxy_policy=TrustedProxyPolicy(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await mfa_router._limit_verification(
            request_for("/auth/mfa/verify"),
            runtime,
            user_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == mfa_router.GENERIC_UNAVAILABLE
