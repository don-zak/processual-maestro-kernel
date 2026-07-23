from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace

import pytest

from processual_api.auth import recovery_email_runtime
from processual_api.auth.recovery_email_runtime import (
    RecoveryEmailRuntimeUnavailableError,
    build_recovery_email_runtime,
)


class FakeRedis:
    async def eval(self, *values):
        return [0, 0, 1]


def _config():
    return SimpleNamespace(
        auth_token_pepper="t" * 32,
        auth_rate_limit_pepper="r" * 32,
        auth_delivery_current_key_version="v1",
        auth_delivery_key_ring_json=json.dumps(
            {
                "v1": base64.b64encode(
                    b"k" * 32
                ).decode()
            }
        ),
        auth_registration_min_response_ms=0,
        auth_trusted_proxy_cidrs=(),
        auth_trusted_proxy_max_hops=1,
    )


def test_runtime_builds_service_without_session_issuer(
    monkeypatch,
):
    monkeypatch.setattr(
        recovery_email_runtime,
        "get_redis",
        lambda: _async_value(FakeRedis()),
    )
    monkeypatch.setattr(
        recovery_email_runtime,
        "get_session_factory",
        lambda: object(),
    )

    runtime = asyncio.run(
        build_recovery_email_runtime(_config())
    )

    assert runtime.service is not None
    assert runtime.rate_limiter is not None
    assert not hasattr(runtime, "session_service")
    assert not hasattr(runtime, "access_token_service")


def test_runtime_fails_closed_without_redis(
    monkeypatch,
):
    monkeypatch.setattr(
        recovery_email_runtime,
        "get_redis",
        lambda: _async_value(None),
    )

    with pytest.raises(
        RecoveryEmailRuntimeUnavailableError
    ):
        asyncio.run(
            build_recovery_email_runtime(_config())
        )


def test_runtime_rejects_short_token_pepper(
    monkeypatch,
):
    config = _config()
    config.auth_token_pepper = "short"

    monkeypatch.setattr(
        recovery_email_runtime,
        "get_redis",
        lambda: _async_value(FakeRedis()),
    )

    with pytest.raises(
        RecoveryEmailRuntimeUnavailableError
    ):
        asyncio.run(
            build_recovery_email_runtime(config)
        )


async def _async_value(value):
    return value
