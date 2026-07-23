from __future__ import annotations

import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from processual_api.auth.rate_limit import (
    AuthRateLimitDecision,
)
from processual_api.auth.recovery_email_router import (
    get_recovery_email_runtime,
    platform_admin_step_up_dependency,
    router,
)


class FakeRateLimiter:
    def __init__(
        self,
        *,
        allowed=True,
    ) -> None:
        self.allowed = allowed
        self.calls = []

    async def consume(self, **values):
        self.calls.append(values)
        return AuthRateLimitDecision(
            allowed=self.allowed,
            retry_after_seconds=17,
            remaining=1 if self.allowed else 0,
        )


class FakeProxyPolicy:
    max_forwarded_hops = 1

    def is_trusted(self, peer) -> bool:
        return False


class FakeService:
    def __init__(self) -> None:
        self.issue_calls = []
        self.verify_calls = []

    async def issue(self, **values):
        self.issue_calls.append(values)
        return SimpleNamespace()

    async def verify(self, **values):
        self.verify_calls.append(values)
        return SimpleNamespace()


def _client(*, allowed=True):
    service = FakeService()
    limiter = FakeRateLimiter(allowed=allowed)
    runtime = SimpleNamespace(
        service=service,
        rate_limiter=limiter,
        proxy_policy=FakeProxyPolicy(),
        minimum_response_seconds=0,
    )

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[
        get_recovery_email_runtime
    ] = lambda: runtime

    app.dependency_overrides[
        platform_admin_step_up_dependency
    ] = lambda: {
        "user_id": str(uuid.uuid4()),
        "session_type": "identity_user",
    }

    return (
        TestClient(
            app,
            client=("198.51.100.7", 50000),
        ),
        service,
        limiter,
    )


def test_issue_requires_step_up_dependency():
    paths = {
        route.path: route
        for route in router.routes
    }

    issue = paths[
        "/auth/recovery-email/verification"
    ]
    resend = paths[
        "/auth/recovery-email/resend"
    ]

    assert issue.dependant.dependencies
    assert resend.dependant.dependencies


def test_issue_returns_generic_accepted_response():
    client, service, limiter = _client()

    response = client.post(
        "/auth/recovery-email/verification"
    )

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "next_action": "check_recovery_email",
    }
    assert len(service.issue_calls) == 1
    assert service.issue_calls[0][
        "recent_step_up"
    ] is True
    assert limiter.calls[0]["action"] == (
        "recovery_email_issue"
    )


def test_resend_uses_same_safe_issue_contract():
    client, service, _ = _client()

    response = client.post(
        "/auth/recovery-email/resend"
    )

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert len(service.issue_calls) == 1


def test_public_verify_returns_generic_processed_response():
    client, service, limiter = _client()

    response = client.post(
        "/auth/recovery-email/verify",
        json={"token": "raw-recovery-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "processed"
    }
    assert response.headers["cache-control"] == (
        "no-store"
    )
    assert service.verify_calls == [
        {"raw_token": "raw-recovery-token"}
    ]
    assert limiter.calls[0]["action"] == (
        "recovery_email_verify"
    )
    assert "access_token" not in response.json()
    assert "refresh_token" not in response.json()


def test_verify_rate_limit_does_not_call_service():
    client, service, _ = _client(allowed=False)

    response = client.post(
        "/auth/recovery-email/verify",
        json={"token": "rate-limited-token"},
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "17"
    assert service.verify_calls == []


def test_verify_validation_does_not_reflect_token():
    client, _, _ = _client()

    response = client.post(
        "/auth/recovery-email/verify",
        json={"token": ""},
    )

    assert response.status_code == 422
    assert "token" not in response.text
