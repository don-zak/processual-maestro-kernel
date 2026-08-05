from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest

import processual_api.admin_marketplace.runtime as runtime_module
from processual_api.admin_marketplace.runtime import (
    AdminMarketplaceRuntimeUnavailableError,
    _payment_destination_keys,
    build_admin_marketplace_runtime,
)


def _config(**updates):
    values = {
        "auth_mfa_step_up_seconds": 300,
        "admin_marketplace_payment_destination_key_ring_json": json.dumps(
            {"payment-v1": base64.b64encode(b"p" * 32).decode()}
        ),
        "admin_marketplace_payment_destination_current_key_version": ("payment-v1"),
    }
    values.update(updates)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_runtime_wires_real_payment_destination_cipher(monkeypatch) -> None:
    monkeypatch.setattr(runtime_module, "get_session_factory", lambda: object())

    runtime = await build_admin_marketplace_runtime(_config())

    assert runtime.eligibility_service is not None
    assert runtime.payment_destination_service is not None
    assert runtime.payment_verification_service is not None
    assert runtime.subscription_activation_service is not None


@pytest.mark.asyncio
async def test_missing_payment_key_fails_closed_only_for_payment_admin(
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime_module, "get_session_factory", lambda: object())

    runtime = await build_admin_marketplace_runtime(
        _config(
            admin_marketplace_payment_destination_key_ring_json=None,
            admin_marketplace_payment_destination_current_key_version=None,
        )
    )

    assert runtime.eligibility_service is not None
    assert runtime.payment_destination_service is None


@pytest.mark.parametrize(
    "raw_json",
    (None, "{}", "[]", "not-json", '{"v1":"not-base64"}'),
)
def test_payment_destination_key_authority_rejects_invalid_values(
    raw_json,
) -> None:
    with pytest.raises(AdminMarketplaceRuntimeUnavailableError):
        _payment_destination_keys(raw_json)
