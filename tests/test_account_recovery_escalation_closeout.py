from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from processual_api.auth.account_recovery_escalation_router import (
    get_account_recovery_escalation_runtime,
    platform_admin_step_up_dependency,
)
from processual_api.auth.account_recovery_router import router
from processual_api.auth.rate_limit import TrustedProxyPolicy
from processual_api.db.session import get_session


MIGRATION = Path("alembic/versions/20260821_0057_account_recovery_escalations.py")
LOGIN_ESCALATION_UI = Path("processual_api/static/js/login_recovery_escalation.js")
ADMIN_ESCALATION_UI = Path("processual_api/static/js/admin_account_recovery_escalations.js")
SECURITY_HEADERS = Path("processual_api/middleware/security_headers.py")
VQ_EXTENDED = Path("qualification/vq1_ui_state_matrix_extended.py")
ESCALATION_ROUTER = Path("processual_api/auth/account_recovery_escalation_router.py")


class _Mappings:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Result:
    def __init__(self, rows=(), rowcount=1):
        self._rows = rows
        self.rowcount = rowcount

    def mappings(self):
        return _Mappings(self._rows)


class FakeSession:
    def __init__(self):
        self.calls = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement, values=None):
        sql = str(statement)
        self.calls.append((sql, dict(values or {})))
        if "SELECT id, claimed_login" in sql:
            return _Result(
                rows=(
                    {
                        "id": "11111111-1111-4111-8111-111111111111",
                        "claimed_login": "owner@example.test",
                        "contact_email": "safe@example.test",
                        "organization_ref": "org-safe",
                        "reason": "lost_recovery_email",
                        "state": "pending",
                        "created_at": "2026-08-21T00:00:00Z",
                        "reviewed_at": None,
                        "resolution": None,
                    },
                )
            )
        return _Result(rowcount=1)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class FakeLimiter:
    def __init__(self, *, allowed: bool = True):
        self.allowed = allowed
        self.calls = []

    async def consume(self, **values):
        self.calls.append(values)
        return SimpleNamespace(
            allowed=self.allowed,
            retry_after_seconds=37 if not self.allowed else 0,
            remaining=4 if self.allowed else 0,
        )


def _client(*, rate_limit_allowed: bool = True):
    fake = FakeSession()
    limiter = FakeLimiter(allowed=rate_limit_allowed)
    runtime = SimpleNamespace(
        rate_limiter=limiter,
        proxy_policy=TrustedProxyPolicy(),
    )
    app = FastAPI()

    @app.middleware("http")
    async def fixed_peer(request: Request, call_next):
        request.scope["client"] = ("198.51.100.77", 47007)
        return await call_next(request)

    app.include_router(router)
    app.dependency_overrides[get_session] = lambda: fake
    app.dependency_overrides[get_account_recovery_escalation_runtime] = lambda: runtime
    app.dependency_overrides[platform_admin_step_up_dependency] = lambda: {
        "user_id": "22222222-2222-4222-8222-222222222222",
        "session_type": "identity_user",
    }
    return TestClient(app), fake, limiter


def test_public_escalation_is_persistent_rate_limited_and_grants_no_authority() -> None:
    client, fake, limiter = _client()
    response = client.post(
        "/auth/account-recovery/escalations",
        json={
            "claimed_login": "owner@example.test",
            "contact_email": "safe@example.test",
            "organization_ref": "org-safe",
            "reason": "lost_recovery_email",
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["next_action"] == "administrator_review"
    assert payload["authority_granted"] is False
    assert fake.commits == 1
    assert any("INSERT INTO auth_account_recovery_escalations" in sql for sql, _ in fake.calls)
    assert limiter.calls == [
        {
            "action": "account_recovery_escalation",
            "subjects": {
                "ip": "198.51.100.77",
                "login": "owner@example.test",
            },
            "rules": limiter.calls[0]["rules"],
        }
    ]
    assert {rule.dimension for rule in limiter.calls[0]["rules"]} == {"ip", "login"}


def test_public_escalation_rate_limit_fails_before_queue_write() -> None:
    client, fake, _ = _client(rate_limit_allowed=False)
    response = client.post(
        "/auth/account-recovery/escalations",
        json={
            "claimed_login": "owner@example.test",
            "contact_email": "safe@example.test",
            "reason": "lost_recovery_email",
        },
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "37"
    assert response.headers["cache-control"] == "no-store"
    assert fake.calls == []
    assert fake.commits == 0


def test_public_escalation_rejects_secret_shaped_extra_fields() -> None:
    client, _, _ = _client()
    response = client.post(
        "/auth/account-recovery/escalations",
        json={
            "claimed_login": "owner@example.test",
            "contact_email": "safe@example.test",
            "reason": "lost_authenticator",
            "password": "must-never-be-accepted",
            "mfa_code": "123456",
        },
    )

    assert response.status_code == 422
    assert "must-never-be-accepted" not in response.text
    assert "123456" not in response.text


def test_admin_review_queue_and_decision_never_mutate_identity_authority() -> None:
    client, fake, _ = _client()
    listed = client.get("/auth/account-recovery/escalations?state=pending")
    decided = client.post(
        "/auth/account-recovery/escalations/11111111-1111-4111-8111-111111111111/decision",
        json={"state": "resolved", "resolution": "recovery_channel_reviewed"},
    )

    assert listed.status_code == 200
    assert listed.json()["authority_granted"] is False
    assert len(listed.json()["requests"]) == 1
    assert decided.status_code == 200
    assert decided.json() == {
        "status": "processed",
        "request_id": "11111111-1111-4111-8111-111111111111",
        "state": "resolved",
        "authority_granted": False,
        "password_reset_performed": False,
        "mfa_bypassed": False,
    }
    update_sql = next(sql for sql, _ in fake.calls if "UPDATE auth_account_recovery_escalations" in sql)
    assert "identity_users" not in update_sql
    assert "auth_mfa" not in update_sql


def test_escalation_migration_is_durable_and_downgrade_is_data_guarded() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260821_0057"' in source
    assert 'down_revision: str | None = "20260818_0056"' in source
    assert 'TABLE = "auth_account_recovery_escalations"' in source
    assert "state IN ('pending','resolved','rejected')" in source
    assert "Downgrade blocked: durable account recovery escalation rows exist" in source


def test_login_and_admin_surfaces_expose_only_governed_recovery_actions() -> None:
    login = LOGIN_ESCALATION_UI.read_text(encoding="utf-8")
    admin = ADMIN_ESCALATION_UI.read_text(encoding="utf-8")

    assert "Contact administrator" in login
    assert "'/auth/account-recovery/escalations'" in login
    assert "Do not enter passwords, MFA codes, recovery codes, API keys" in login
    assert "authority_granted !== false" in login

    assert "Account Recovery Requests" in admin
    assert "/auth/account-recovery/escalations?state=pending" in admin
    assert "password_reset_performed !== false" in admin
    assert "mfa_bypassed !== false" in admin
    assert "Recent platform-admin MFA step-up is required" in admin


def test_escalation_router_reuses_account_recovery_rate_limit_authority() -> None:
    source = ESCALATION_ROUTER.read_text(encoding="utf-8")

    assert "ACCOUNT_RECOVERY_START_RULES" in source
    assert 'action="account_recovery_escalation"' in source
    assert '"ip": _client_ip(request, runtime)' in source
    assert '"login": payload.claimed_login' in source
    assert "AuthRateLimitUnavailableError" in source
    assert "Account recovery escalation request rate limit exceeded" in source


def test_mfa_pending_token_is_confined_to_mfa_completion_endpoints() -> None:
    source = SECURITY_HEADERS.read_text(encoding="utf-8")

    assert '"auth:mfa" not in scopes' in source
    assert '"/auth/mfa/totp/enroll"' in source
    assert '"/auth/mfa/totp/confirm"' in source
    assert '"/auth/mfa/verify"' in source
    assert '"/auth/session/refresh"' in source
    assert "MFA enrollment or verification must be completed before normal account access" in source


def test_vq_controlled_mfa_state_intercepts_status_gate() -> None:
    source = VQ_EXTENDED.read_text(encoding="utf-8")

    assert 'status_pattern = "**/auth/mfa/status"' in source
    assert '"enabled": True' in source
    assert "page.unroute(status_pattern)" in source
