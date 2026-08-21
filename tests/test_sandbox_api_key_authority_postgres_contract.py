from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from processual_api.services import sandbox_api_key_authority as authority
from processual_api.services.sandbox_api_key_persistence import SandboxApiKeyAuthority


class _Session:
    def __init__(self) -> None:
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


class _Factory:
    def __init__(self, session: _Session) -> None:
        self.session = session

    def __call__(self) -> _Session:
        return self.session


def _key(*, expires_at: datetime | None = None) -> SandboxApiKeyAuthority:
    return SandboxApiKeyAuthority(
        id=uuid.uuid4(),
        key_hash="stored-hash-only",
        key_prefix="pmk_sandbox_",
        client_ref="customer-01",
        owner_user_ref="user-01",
        subscription_id=uuid.uuid4(),
        plan_id="pilot_starter",
        operational_profile_id="service_integration_read_only",
        scopes_json=json.dumps(["read:health"]),
        label="qualification",
        purpose="sandbox qualification",
        issued_to="customer-01",
        issued_by_actor_ref="platform-admin-01",
        environment="sandbox",
        status="enabled",
        expires_at=expires_at or (datetime.now(UTC) + timedelta(days=1)),
        usage_count=0,
    )


def _patch_repositories(monkeypatch, key, *, access_stage: str) -> _Session:
    session = _Session()
    monkeypatch.setattr(authority, "get_session_factory", lambda: _Factory(session))

    class _Keys:
        def __init__(self, _session) -> None:
            pass

        async def candidates_by_prefix(self, prefix: str, *, for_update: bool = False):
            assert prefix == "pmk_sandbox_"
            assert for_update is True
            return [key]

    class _Runtime:
        def __init__(self, _session) -> None:
            pass

        async def get_by_subscription_id(self, subscription_id, *, for_update: bool = False):
            assert subscription_id == key.subscription_id
            assert for_update is True
            return SimpleNamespace(customer_ref=key.client_ref, access_stage=access_stage)

    monkeypatch.setattr(authority, "SqlAlchemySandboxApiKeyRepository", _Keys)
    monkeypatch.setattr(authority, "SqlAlchemySubscriptionRuntimeRepository", _Runtime)
    monkeypatch.setattr(
        authority,
        "_verify_stored_key",
        lambda raw, hashed: raw == "pmk_sandbox_secret" and hashed == key.key_hash,
    )
    return session


def test_durable_sandbox_key_requires_active_subscription_runtime(monkeypatch) -> None:
    key = _key()
    session = _patch_repositories(monkeypatch, key, access_stage="active")

    identity = asyncio.run(authority.verify_durable_sandbox_api_key("pmk_sandbox_secret"))

    assert identity is not None
    assert identity["subscription_id"] == str(key.subscription_id)
    assert identity["environment"] == "sandbox"
    assert identity["production_allowed"] is False
    assert identity["runtime_connector_approved"] is False
    assert identity["scopes"] == ["read:health"]
    assert key.usage_count == 1
    assert session.commits == 1


def test_durable_sandbox_key_is_explicitly_denied_when_subscription_is_suspended(
    monkeypatch,
) -> None:
    key = _key()
    session = _patch_repositories(monkeypatch, key, access_stage="suspended")

    with pytest.raises(
        authority.DurableSandboxApiKeyDenied,
        match="subscription_not_active",
    ):
        asyncio.run(authority.verify_durable_sandbox_api_key("pmk_sandbox_secret"))

    assert key.usage_count == 0
    assert session.commits == 0


def test_revoked_durable_key_is_explicit_denial_not_no_match(monkeypatch) -> None:
    key = _key()
    key.mark_revoked()
    session = _patch_repositories(monkeypatch, key, access_stage="active")

    with pytest.raises(
        authority.DurableSandboxApiKeyDenied,
        match="revoked_or_disabled",
    ):
        asyncio.run(authority.verify_durable_sandbox_api_key("pmk_sandbox_secret"))

    assert key.usage_count == 0
    assert session.commits == 0


def test_durable_sandbox_key_expires_before_runtime_authority(monkeypatch) -> None:
    key = _key(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    session = _patch_repositories(monkeypatch, key, access_stage="active")

    with pytest.raises(authority.DurableSandboxApiKeyDenied, match="key_expired"):
        asyncio.run(authority.verify_durable_sandbox_api_key("pmk_sandbox_secret"))

    assert key.status == "expired"
    assert key.usage_count == 0
    assert session.commits == 1


def test_non_matching_candidate_allows_no_match_result(monkeypatch) -> None:
    key = _key()
    session = _patch_repositories(monkeypatch, key, access_stage="active")

    identity = asyncio.run(authority.verify_durable_sandbox_api_key("pmk_sandbox_other"))

    assert identity is None
    assert key.usage_count == 0
    assert session.commits == 0
