from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest

import processual_api.auth.delivery_runtime as runtime_module
from processual_api.auth.delivery_runtime import (
    DeliveryRuntimeUnavailableError,
    build_delivery_runtime,
)


def _config(**updates):
    values = {
        "auth_delivery_key_ring_json": json.dumps(
            {"v1": base64.b64encode(b"k" * 32).decode()}
        ),
        "auth_delivery_current_key_version": "v1",
        "auth_delivery_provider_url": "https://provider.example.test/send",
        "auth_delivery_provider_token": "p" * 32,
        "auth_public_base_url": "https://accounts.example.test",
        "auth_delivery_batch_size": 25,
        "auth_delivery_lease_seconds": 300,
        "auth_delivery_max_attempts": 8,
        "auth_delivery_retry_base_seconds": 30,
        "auth_delivery_retry_max_seconds": 3600,
        "auth_delivery_request_timeout_seconds": 10.0,
    }
    values.update(updates)
    return SimpleNamespace(**values)


def test_delivery_runtime_wires_fail_closed_authorities(monkeypatch):
    monkeypatch.setattr(runtime_module, "get_session_factory", lambda: object())

    runtime = build_delivery_runtime(_config())

    assert runtime.dispatcher is not None


@pytest.mark.parametrize(
    "updates",
    (
        {"auth_delivery_key_ring_json": None},
        {"auth_delivery_current_key_version": "missing"},
        {"auth_delivery_provider_url": "http://provider.example.test/send"},
        {"auth_delivery_provider_token": "short"},
        {"auth_public_base_url": "http://accounts.example.test"},
        {"auth_delivery_batch_size": 0},
        {"auth_delivery_lease_seconds": 5},
        {"auth_delivery_max_attempts": 0},
        {"auth_delivery_retry_max_seconds": 1},
        {"auth_delivery_request_timeout_seconds": 0},
    ),
)
def test_delivery_runtime_rejects_missing_or_unsafe_authority(monkeypatch, updates):
    monkeypatch.setattr(runtime_module, "get_session_factory", lambda: object())

    with pytest.raises(DeliveryRuntimeUnavailableError):
        build_delivery_runtime(_config(**updates))
