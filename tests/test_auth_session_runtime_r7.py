from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import processual_api.auth.session_runtime as runtime_module
from processual_api.auth.session_runtime import (
    SessionRuntimeUnavailableError,
    build_session_runtime,
)


def _config(**updates):
    values = {
        "auth_token_pepper": "t" * 32,
        "auth_rate_limit_pepper": "r" * 32,
        "auth_trusted_proxy_cidrs": (),
        "auth_trusted_proxy_max_hops": 8,
        "auth_login_min_response_ms": 350,
        "auth_access_token_seconds": 900,
        "auth_refresh_token_days": 30,
        "auth_failed_login_limit": 5,
        "auth_login_lockout_seconds": 900,
    }
    values.update(updates)
    return SimpleNamespace(**values)


def _dependencies(monkeypatch, *, redis=object()):
    async def get_redis():
        return redis

    monkeypatch.setattr(runtime_module, "get_redis", get_redis)
    monkeypatch.setattr(runtime_module, "get_session_factory", lambda: object())
    monkeypatch.setattr(runtime_module, "_dummy_password_hash", lambda: "dummy-hash")


def test_session_runtime_wires_fail_closed_authorities(monkeypatch):
    _dependencies(monkeypatch)

    runtime = asyncio.run(build_session_runtime(_config()))

    assert runtime.service is not None
    assert runtime.minimum_response_seconds == 0.35


@pytest.mark.parametrize(
    "updates",
    (
        {"auth_token_pepper": None},
        {"auth_rate_limit_pepper": "short"},
        {"auth_trusted_proxy_cidrs": ("0.0.0.0/0",)},
        {"auth_trusted_proxy_max_hops": 0},
        {"auth_login_min_response_ms": -1},
        {"auth_access_token_seconds": 30},
        {"auth_refresh_token_days": 0},
        {"auth_failed_login_limit": 1},
        {"auth_login_lockout_seconds": 1},
    ),
)
def test_session_runtime_rejects_missing_or_unsafe_authority(monkeypatch, updates):
    _dependencies(monkeypatch)

    with pytest.raises(SessionRuntimeUnavailableError):
        asyncio.run(build_session_runtime(_config(**updates)))


def test_session_runtime_requires_redis(monkeypatch):
    _dependencies(monkeypatch, redis=None)

    with pytest.raises(SessionRuntimeUnavailableError):
        asyncio.run(build_session_runtime(_config()))
