from __future__ import annotations

import uuid
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from processual_api.auth.mfa_contracts import MfaEnrollment, MfaStatus
from processual_api.auth.mfa_router import get_mfa_runtime, router
from processual_api.auth.mfa_runtime import MfaRuntime
from processual_api.auth.rate_limit import TrustedProxyPolicy
from processual_api.auth.session_router import get_identity_user


class AllowingLimiter:
    def __init__(self) -> None:
        self.calls = []

    async def consume(self, **values):
        self.calls.append(values)
        return SimpleNamespace(allowed=True, retry_after_seconds=0, remaining=5)


class FakeMfaService:
    def __init__(self) -> None:
        self.calls = []

    async def status(self, **values):
        self.calls.append(("status", values))
        return MfaStatus(True, False, 8, False)

    async def enroll(self, **values):
        self.calls.append(("enroll", values))
        return MfaEnrollment("SECRET-NOT-LOGGED", "otpauth://totp/test")

    async def confirm_enrollment(self, **values):
        self.calls.append(("confirm", values))
        return ("AAAA-BBBB-CCCC-DDDD", "EEEE-FFFF-GGGG-HHHH")

    async def verify(self, **values):
        self.calls.append(("verify", values))

    async def regenerate_recovery_codes(self, **values):
        self.calls.append(("regenerate", values))
        return ("IIII-JJJJ-KKKK-LLLL",)

    async def disable(self, **values):
        self.calls.append(("disable", values))


def _client():
    service = FakeMfaService()
    limiter = AllowingLimiter()
    runtime = MfaRuntime(
        service=service,
        rate_limiter=limiter,
        proxy_policy=TrustedProxyPolicy(),
    )
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    app = FastAPI()

    @app.middleware("http")
    async def fixed_peer(request: Request, call_next):
        request.scope["client"] = ("198.51.100.49", 47005)
        return await call_next(request)

    app.include_router(router)
    app.dependency_overrides[get_mfa_runtime] = lambda: runtime
    app.dependency_overrides[get_identity_user] = lambda: {
        "user_id": str(user_id),
        "session_id": str(session_id),
        "session_type": "identity_user",
        "scopes": ["auth:mfa"],
    }
    return TestClient(app, base_url="https://testserver"), service, limiter


def test_enrollment_secret_is_no_store_and_confirmation_returns_codes_once():
    client, service, limiter = _client()

    enrolled = client.post("/auth/mfa/totp/enroll", json={"label": "Primary"})
    confirmed = client.post("/auth/mfa/totp/confirm", json={"code": "123456"})

    assert enrolled.status_code == 200
    assert enrolled.json()["secret"] == "SECRET-NOT-LOGGED"
    assert enrolled.headers["cache-control"] == "no-store"
    assert confirmed.status_code == 200
    assert len(confirmed.json()["recovery_codes"]) == 2
    assert confirmed.headers["cache-control"] == "no-store"
    assert limiter.calls[0]["subjects"]
    assert service.calls[1][0] == "confirm"


def test_verify_accepts_exactly_one_credential_and_sanitizes_invalid_payload():
    client, service, _ = _client()

    accepted = client.post("/auth/mfa/verify", json={"recovery_code": "AAAA-BBBB-CCCC-DDDD"})
    rejected = client.post(
        "/auth/mfa/verify",
        json={
            "code": "123456",
            "recovery_code": "SECRET-MUST-NOT-BE-REFLECTED",
        },
    )

    assert accepted.status_code == 200
    assert accepted.json() == {"status": "processed"}
    assert rejected.status_code == 422
    assert rejected.json() == {"detail": "Invalid MFA request."}
    assert "SECRET-MUST-NOT-BE-REFLECTED" not in rejected.text
    assert [call[0] for call in service.calls] == ["verify"]


def test_status_regenerate_and_disable_use_authoritative_identity():
    client, service, _ = _client()

    status = client.get("/auth/mfa/status")
    regenerated = client.post("/auth/mfa/recovery-codes/regenerate")
    disabled = client.post("/auth/mfa/disable")

    assert status.json() == {
        "enabled": True,
        "pending_enrollment": False,
        "recovery_codes_remaining": 8,
        "step_up_satisfied": False,
    }
    assert regenerated.headers["cache-control"] == "no-store"
    assert disabled.json() == {"status": "processed"}
    assert [call[0] for call in service.calls] == ["status", "regenerate", "disable"]
