from __future__ import annotations

import time
from dataclasses import dataclass, field

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from processual_api.auth.rate_limit import (
    AuthRateLimitDecision,
    AuthRateLimitUnavailableError,
    TrustedProxyPolicy,
)
from processual_api.auth.registration_router import (
    get_registration_runtime,
    router,
)
from processual_api.auth.registration_runtime import RegistrationRuntime
from processual_api.middleware.request_id import RequestIDMiddleware


@dataclass
class FakeLimiter:
    decisions: list[AuthRateLimitDecision] = field(default_factory=list)
    unavailable: bool = False
    calls: list[dict] = field(default_factory=list)

    async def consume(self, **values):
        self.calls.append(values)
        if self.unavailable:
            raise AuthRateLimitUnavailableError("redis detail must stay private")
        return self.decisions.pop(0) if self.decisions else AuthRateLimitDecision(True, 0, 1)


@dataclass
class FakeService:
    commands: list = field(default_factory=list)
    unavailable: bool = False

    async def register(self, command):
        self.commands.append(command)
        if self.unavailable:
            raise RuntimeError("database detail must stay private")


@dataclass
class FakeVerificationService:
    verified: list[str] = field(default_factory=list)
    resent: list[str] = field(default_factory=list)
    unavailable: bool = False

    async def verify(self, token):
        self.verified.append(token)
        if self.unavailable:
            raise RuntimeError("verification detail must stay private")

    async def resend(self, email):
        self.resent.append(email)
        if self.unavailable:
            raise RuntimeError("resend detail must stay private")


def _client(runtime: RegistrationRuntime) -> TestClient:
    app = FastAPI()

    @app.middleware("http")
    async def fixed_peer(request: Request, call_next):
        request.scope["client"] = ("198.51.100.10", 42000)
        return await call_next(request)

    app.add_middleware(RequestIDMiddleware)
    app.include_router(router)
    app.dependency_overrides[get_registration_runtime] = lambda: runtime
    return TestClient(app, raise_server_exceptions=False)


def _runtime(*, limiter=None, service=None, verification_service=None, floor=0.0) -> RegistrationRuntime:
    return RegistrationRuntime(
        service=service or FakeService(),
        rate_limiter=limiter or FakeLimiter(),
        proxy_policy=TrustedProxyPolicy(),
        minimum_response_seconds=floor,
        email_verification_service=verification_service or FakeVerificationService(),
    )


def _individual_payload(**updates):
    payload = {
        "email": "  Person@Example.COM ",
        "full_name": "Example Person",
        "password": "correct horse battery staple",
        "accepted_terms_version": "2026-07",
    }
    payload.update(updates)
    return payload


def test_individual_registration_uses_ip_then_normalized_email_and_returns_202():
    limiter = FakeLimiter()
    service = FakeService()
    client = _client(_runtime(limiter=limiter, service=service))

    response = client.post(
        "/auth/register",
        json=_individual_payload(),
        headers={"X-Request-ID": "registration-test-1"},
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted", "next_action": "check_email"}
    assert response.headers["X-Request-ID"] == "registration-test-1"
    assert [tuple(call["subjects"]) for call in limiter.calls] == [("ip",), ("email",)]
    assert limiter.calls[1]["subjects"]["email"] == "person@example.com"
    assert service.commands[0].email == "person@example.com"


def test_email_limit_is_generic_202_and_does_not_call_registration_service():
    limiter = FakeLimiter(
        decisions=[
            AuthRateLimitDecision(True, 0, 3),
            AuthRateLimitDecision(False, 7200, 0),
        ]
    )
    service = FakeService()
    response = _client(_runtime(limiter=limiter, service=service)).post(
        "/auth/register",
        json=_individual_payload(),
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted", "next_action": "check_email"}
    assert "Retry-After" not in response.headers
    assert service.commands == []


def test_ip_limit_is_the_only_rejection_that_exposes_retry_after():
    limiter = FakeLimiter(decisions=[AuthRateLimitDecision(False, 73, 0)])
    service = FakeService()
    response = _client(_runtime(limiter=limiter, service=service)).post(
        "/auth/register",
        json=_individual_payload(),
    )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "73"
    assert len(limiter.calls) == 1
    assert service.commands == []


def test_redis_and_database_failures_are_generic_503():
    redis_response = _client(_runtime(limiter=FakeLimiter(unavailable=True))).post(
        "/auth/register",
        json=_individual_payload(),
    )
    database_response = _client(_runtime(service=FakeService(unavailable=True))).post(
        "/auth/register",
        json=_individual_payload(),
    )

    assert redis_response.status_code == 503
    assert database_response.status_code == 503
    assert (
        redis_response.json() == database_response.json() == {"detail": "Registration service temporarily unavailable."}
    )
    assert "private" not in redis_response.text
    assert "private" not in database_response.text


def test_sensitive_validation_is_generic_and_forbids_authority_fields():
    secret = "do-not-reflect-this-password"
    response = _client(_runtime()).post(
        "/auth/register",
        json=_individual_payload(password=secret, role="platform_admin", plan_id="enterprise"),
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid registration request."}
    assert secret not in response.text
    assert "platform_admin" not in response.text
    assert "enterprise" not in response.text


def test_organization_route_assigns_only_server_owned_mode():
    service = FakeService()
    payload = _individual_payload(organization_name="Example Org")
    response = _client(_runtime(service=service)).post(
        "/auth/register/organization",
        json=payload,
    )

    assert response.status_code == 202
    assert service.commands[0].mode.value == "organization"
    assert service.commands[0].organization_name == "Example Org"


def test_public_config_contains_no_roles_plans_or_provider_state():
    response = _client(_runtime()).get("/auth/registration/config")

    assert response.status_code == 200
    assert response.json() == {
        "registration_modes": ["individual", "organization"],
        "password_min_length": 12,
        "password_max_length": 1024,
        "email_verification_required": True,
    }
    assert not {"roles", "plans", "provider"}.intersection(response.json())


def test_generic_202_paths_apply_the_same_response_time_floor():
    floor = 0.04
    accepted_client = _client(_runtime(floor=floor))
    limited_client = _client(
        _runtime(
            floor=floor,
            limiter=FakeLimiter(
                decisions=[
                    AuthRateLimitDecision(True, 0, 1),
                    AuthRateLimitDecision(False, 60, 0),
                ]
            ),
        )
    )

    started = time.perf_counter()
    accepted_response = accepted_client.post("/auth/register", json=_individual_payload())
    accepted_elapsed = time.perf_counter() - started
    started = time.perf_counter()
    limited_response = limited_client.post("/auth/register", json=_individual_payload())
    limited_elapsed = time.perf_counter() - started

    assert accepted_response.status_code == limited_response.status_code == 202
    assert accepted_response.json() == limited_response.json()
    assert accepted_elapsed >= floor * 0.9
    assert limited_elapsed >= floor * 0.9


def test_verify_email_is_rate_limited_and_returns_only_generic_processed():
    limiter = FakeLimiter()
    verification = FakeVerificationService()
    response = _client(
        _runtime(limiter=limiter, verification_service=verification)
    ).post("/auth/verify-email", json={"token": "raw-secret-token"})

    assert response.status_code == 200
    assert response.json() == {"status": "processed"}
    assert verification.verified == ["raw-secret-token"]
    assert tuple(limiter.calls[0]["subjects"]) == ("ip", "token")


def test_verify_email_replay_throttling_is_429_without_service_call():
    limiter = FakeLimiter(decisions=[AuthRateLimitDecision(False, 91, 0)])
    verification = FakeVerificationService()
    response = _client(
        _runtime(limiter=limiter, verification_service=verification)
    ).post("/auth/verify-email", json={"token": "raw-secret-token"})

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "91"
    assert verification.verified == []
    assert "raw-secret-token" not in response.text


def test_resend_is_ip_then_normalized_email_and_generic_202():
    limiter = FakeLimiter()
    verification = FakeVerificationService()
    response = _client(
        _runtime(limiter=limiter, verification_service=verification)
    ).post("/auth/verification/resend", json={"email": " Person@Example.COM "})

    assert response.status_code == 202
    assert response.json() == {"status": "accepted", "next_action": "check_email"}
    assert verification.resent == ["person@example.com"]
    assert [tuple(call["subjects"]) for call in limiter.calls] == [("ip",), ("email",)]


def test_resend_email_limit_is_generic_202_without_service_call():
    limiter = FakeLimiter(
        decisions=[
            AuthRateLimitDecision(True, 0, 3),
            AuthRateLimitDecision(False, 3600, 0),
        ]
    )
    verification = FakeVerificationService()
    response = _client(
        _runtime(limiter=limiter, verification_service=verification)
    ).post("/auth/verification/resend", json={"email": "person@example.com"})

    assert response.status_code == 202
    assert "Retry-After" not in response.headers
    assert verification.resent == []


def test_verification_validation_does_not_reflect_token_or_authority_fields():
    response = _client(_runtime()).post(
        "/auth/verify-email",
        json={"token": "raw-secret-token", "role": "platform_admin"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid registration request."}
    assert "raw-secret-token" not in response.text
    assert "platform_admin" not in response.text
