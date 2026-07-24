from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from processual_api.auth.account_recovery_router import (
    get_account_recovery_runtime,
    router,
)
from processual_api.auth.account_recovery_service import (
    AccountRecoveryDeniedError,
)
from processual_api.auth.rate_limit import (
    AuthRateLimitDecision,
)
from processual_api.middleware.request_id import (
    RequestIDMiddleware,
)


class FakeRateLimiter:
    def __init__(
        self,
        *,
        decisions=(),
    ) -> None:
        self.decisions = list(decisions)
        self.calls = []

    async def consume(self, **values):
        self.calls.append(values)

        if self.decisions:
            return self.decisions.pop(0)

        return AuthRateLimitDecision(
            allowed=True,
            retry_after_seconds=0,
            remaining=1,
        )


class FakeProxyPolicy:
    max_forwarded_hops = 1

    def is_trusted(self, peer) -> bool:
        return False


class FakeService:
    def __init__(
        self,
        *,
        deny_verify=False,
        fail=False,
    ) -> None:
        self.deny_verify = deny_verify
        self.fail = fail
        self.start_calls = []
        self.verify_calls = []

    async def start(self, **values):
        self.start_calls.append(values)

        if self.fail:
            raise RuntimeError("private database detail")

        return SimpleNamespace(
            accepted=True,
        )

    async def verify(self, **values):
        self.verify_calls.append(values)

        if self.deny_verify:
            raise AccountRecoveryDeniedError("private verification detail")

        if self.fail:
            raise RuntimeError("private database detail")

        return SimpleNamespace(
            request_id=values["request_id"],
            completion_token=("completion-secret-token"),
            completion_expires_at=(
                datetime(
                    2026,
                    7,
                    24,
                    10,
                    tzinfo=UTC,
                )
                + timedelta(minutes=15)
            ),
            password_change_required=True,
            mfa_reenrollment_required=True,
            session_created=False,
            access_token_issued=False,
            refresh_token_issued=False,
        )


def _client(
    *,
    limiter=None,
    service=None,
    floor=0,
):
    runtime = SimpleNamespace(
        service=service or FakeService(),
        rate_limiter=(limiter or FakeRateLimiter()),
        proxy_policy=FakeProxyPolicy(),
        minimum_response_seconds=floor,
    )

    app = FastAPI()

    @app.middleware("http")
    async def fixed_peer(
        request: Request,
        call_next,
    ):
        request.scope["client"] = (
            "198.51.100.10",
            42000,
        )
        return await call_next(request)

    app.add_middleware(RequestIDMiddleware)
    app.include_router(router)

    app.dependency_overrides[get_account_recovery_runtime] = lambda: runtime

    return (
        TestClient(
            app,
            raise_server_exceptions=False,
        ),
        runtime.service,
        runtime.rate_limiter,
    )


def test_start_is_generic_and_uses_ip_then_login():
    client, service, limiter = _client()

    response = client.post(
        "/auth/account-recovery/start",
        json={"login": " Person@Example.COM "},
        headers={"X-Request-ID": "recovery-start-1"},
    )

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "next_action": "check_recovery_email",
    }
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Request-ID"] == "recovery-start-1"

    assert len(limiter.calls) == 2
    assert tuple(limiter.calls[0]["subjects"]) == ("ip",)
    assert tuple(limiter.calls[1]["subjects"]) == ("login",)

    assert service.start_calls == [{"login": "Person@Example.COM"}]


def test_login_limit_remains_generic_202():
    limiter = FakeRateLimiter(
        decisions=(
            AuthRateLimitDecision(
                True,
                0,
                1,
            ),
            AuthRateLimitDecision(
                False,
                3600,
                0,
            ),
        )
    )
    service = FakeService()

    response = _client(
        limiter=limiter,
        service=service,
    )[0].post(
        "/auth/account-recovery/start",
        json={"login": "person@example.com"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == ("accepted")
    assert "Retry-After" not in response.headers
    assert service.start_calls == []


def test_ip_limit_returns_429_without_service_call():
    limiter = FakeRateLimiter(
        decisions=(
            AuthRateLimitDecision(
                False,
                73,
                0,
            ),
        )
    )
    service = FakeService()

    response = _client(
        limiter=limiter,
        service=service,
    )[0].post(
        "/auth/account-recovery/start",
        json={"login": "person@example.com"},
    )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "73"
    assert service.start_calls == []


def test_start_validation_does_not_reflect_input():
    secret = "secret-login@example.com"

    response = _client()[0].post(
        "/auth/account-recovery/start",
        json={
            "login": secret,
            "role": "platform_admin",
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid account recovery request."}
    assert secret not in response.text
    assert "platform_admin" not in response.text


def test_verify_returns_completion_authority_only():
    request_id = uuid.uuid4()

    client, service, limiter = _client()

    response = client.post(
        "/auth/account-recovery/verify",
        json={
            "request_id": str(request_id),
            "token": "raw-verification-token",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "verified"
    assert body["request_id"] == str(request_id)
    assert body["completion_token"] == ("completion-secret-token")
    assert body["password_change_required"] is True
    assert body["mfa_reenrollment_required"] is True
    assert body["session_created"] is False
    assert body["access_token_issued"] is False
    assert body["refresh_token_issued"] is False
    assert response.headers["Cache-Control"] == "no-store"

    assert service.verify_calls == [
        {
            "request_id": request_id,
            "raw_token": "raw-verification-token",
        }
    ]

    assert tuple(limiter.calls[0]["subjects"]) == ("ip", "token")


def test_invalid_verify_is_generic_and_no_store():
    request_id = uuid.uuid4()
    service = FakeService(deny_verify=True)

    response = _client(service=service)[0].post(
        "/auth/account-recovery/verify",
        json={
            "request_id": str(request_id),
            "token": "invalid-token",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Account recovery verification is unavailable."}
    assert "private" not in response.text
    assert "invalid-token" not in response.text
    assert response.headers["Cache-Control"] == "no-store"


def test_verify_validation_hides_token_and_role():
    response = _client()[0].post(
        "/auth/account-recovery/verify",
        json={
            "request_id": "not-a-uuid",
            "token": "raw-secret-token",
            "role": "platform_admin",
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid account recovery request."}
    assert "raw-secret-token" not in response.text
    assert "platform_admin" not in response.text
