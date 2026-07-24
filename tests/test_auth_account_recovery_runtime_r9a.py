from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest

import processual_api.auth.account_recovery_runtime as runtime_module
from processual_api.auth.account_recovery_runtime import (
    AccountRecoveryRuntimeUnavailableError,
    build_account_recovery_runtime,
)


class FakeRedis:
    async def eval(
        self,
        script,
        numkeys,
        *values,
    ):
        return [0, 0, 1]


def _config(**updates):
    values = {
        "auth_token_pepper": "t" * 32,
        "auth_rate_limit_pepper": "r" * 32,
        "auth_delivery_key_ring_json": json.dumps({"v1": base64.b64encode(b"k" * 32).decode()}),
        "auth_delivery_current_key_version": "v1",
        "auth_trusted_proxy_cidrs": ("10.0.0.0/8",),
        "auth_trusted_proxy_max_hops": 4,
        "auth_registration_min_response_ms": 350,
    }
    values.update(updates)

    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_runtime_wires_recovery_authorities(
    monkeypatch,
):
    async def fake_get_redis():
        return FakeRedis()

    monkeypatch.setattr(
        runtime_module,
        "get_redis",
        fake_get_redis,
    )
    monkeypatch.setattr(
        runtime_module,
        "get_session_factory",
        lambda: object(),
    )
    external_revoker = object()
    monkeypatch.setattr(
        runtime_module,
        "_build_external_authority_revoker",
        lambda: external_revoker,
    )

    runtime = await build_account_recovery_runtime(_config())

    assert runtime.service is not None
    assert runtime.service._external_authority_revoker is external_revoker
    assert runtime.rate_limiter is not None
    assert runtime.proxy_policy.max_forwarded_hops == 4
    assert runtime.minimum_response_seconds == 0.35


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "updates",
    (
        {"auth_token_pepper": None},
        {"auth_rate_limit_pepper": "short"},
        {"auth_delivery_key_ring_json": "not-json"},
        {"auth_delivery_current_key_version": "missing"},
        {"auth_trusted_proxy_cidrs": ("0.0.0.0/0",)},
        {"auth_registration_min_response_ms": 6000},
    ),
)
async def test_runtime_fails_closed(
    monkeypatch,
    updates,
):
    async def fake_get_redis():
        return FakeRedis()

    monkeypatch.setattr(
        runtime_module,
        "get_redis",
        fake_get_redis,
    )
    monkeypatch.setattr(
        runtime_module,
        "get_session_factory",
        lambda: object(),
    )
    monkeypatch.setattr(
        runtime_module,
        "_build_external_authority_revoker",
        lambda: object(),
    )

    with pytest.raises(AccountRecoveryRuntimeUnavailableError):
        await build_account_recovery_runtime(_config(**updates))


@pytest.mark.asyncio
async def test_runtime_fails_closed_without_redis(
    monkeypatch,
):
    async def missing_redis():
        return None

    monkeypatch.setattr(
        runtime_module,
        "get_redis",
        missing_redis,
    )

    with pytest.raises(AccountRecoveryRuntimeUnavailableError):
        await build_account_recovery_runtime(_config())


@pytest.mark.asyncio
async def test_runtime_fails_closed_without_external_authority(
    monkeypatch,
):
    async def fake_get_redis():
        return FakeRedis()

    monkeypatch.setattr(
        runtime_module,
        "get_redis",
        fake_get_redis,
    )
    monkeypatch.setattr(
        runtime_module,
        "get_session_factory",
        lambda: object(),
    )

    def unavailable_revoker():
        raise AccountRecoveryRuntimeUnavailableError("external authority unavailable")

    monkeypatch.setattr(
        runtime_module,
        "_build_external_authority_revoker",
        unavailable_revoker,
    )

    with pytest.raises(AccountRecoveryRuntimeUnavailableError):
        await build_account_recovery_runtime(_config())
