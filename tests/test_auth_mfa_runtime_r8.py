from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace

import pytest

import processual_api.auth.mfa_runtime as runtime_module
from processual_api.auth.mfa_runtime import MfaRuntimeUnavailableError, build_mfa_runtime


def _config(**updates):
    values = {
        "auth_mfa_key_ring_json": json.dumps(
            {"v1": base64.b64encode(b"m" * 32).decode()}
        ),
        "auth_mfa_current_key_version": "v1",
        "auth_mfa_issuer": "Processual Maestro",
        "auth_mfa_recovery_code_count": 10,
        "auth_mfa_step_up_seconds": 300,
        "auth_token_pepper": "t" * 32,
        "auth_rate_limit_pepper": "r" * 32,
        "auth_trusted_proxy_cidrs": (),
        "auth_trusted_proxy_max_hops": 8,
    }
    values.update(updates)
    return SimpleNamespace(**values)


def _dependencies(monkeypatch, *, redis=object()):
    async def get_redis():
        return redis

    monkeypatch.setattr(runtime_module, "get_redis", get_redis)
    monkeypatch.setattr(runtime_module, "get_session_factory", lambda: object())


def test_mfa_runtime_wires_independent_crypto_and_rate_limit_authorities(monkeypatch):
    _dependencies(monkeypatch)

    runtime = asyncio.run(build_mfa_runtime(_config()))

    assert runtime.service is not None
    assert runtime.rate_limiter is not None


@pytest.mark.parametrize(
    "updates",
    (
        {"auth_mfa_key_ring_json": None},
        {"auth_mfa_key_ring_json": "not-json"},
        {"auth_mfa_current_key_version": "missing"},
        {"auth_token_pepper": "short"},
        {"auth_rate_limit_pepper": None},
        {"auth_mfa_recovery_code_count": 2},
        {"auth_mfa_step_up_seconds": 30},
        {"auth_trusted_proxy_cidrs": ("0.0.0.0/0",)},
    ),
)
def test_mfa_runtime_rejects_missing_or_unsafe_authority(monkeypatch, updates):
    _dependencies(monkeypatch)

    with pytest.raises(MfaRuntimeUnavailableError):
        asyncio.run(build_mfa_runtime(_config(**updates)))


def test_mfa_runtime_requires_redis(monkeypatch):
    _dependencies(monkeypatch, redis=None)

    with pytest.raises(MfaRuntimeUnavailableError):
        asyncio.run(build_mfa_runtime(_config()))
