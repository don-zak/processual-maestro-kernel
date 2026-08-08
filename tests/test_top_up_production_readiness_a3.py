from __future__ import annotations

import pytest

from processual_api.admin_marketplace.top_up_production_readiness import (
    evaluate_top_up_production_readiness,
    require_top_up_production_readiness,
)

LEMON_KEYS = (
    "MAESTRO_TOP_UP_PURCHASE_ENABLED",
    "LEMONSQUEEZY_API_KEY",
    "LEMONSQUEEZY_STORE_ID",
    "LEMONSQUEEZY_TOP_UP_VARIANT_ID",
    "LEMONSQUEEZY_WEBHOOK_SECRET",
    "LEMONSQUEEZY_CHECKOUT_SUCCESS_URL",
)
LOCAL_KEYS = (
    "MAESTRO_LOCAL_TUNISIA_TOP_UP_ENABLED",
    "MAESTRO_LOCAL_TUNISIA_TOP_UP_ADMIN_ENABLED",
    "MAESTRO_TUNISIA_USD_TND_RATE",
    "MAESTRO_TUNISIA_FX_SOURCE",
    "MAESTRO_TUNISIA_FX_REFERENCE",
    "MAESTRO_TUNISIA_FX_TTL_SECONDS",
)


def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (*LEMON_KEYS, *LOCAL_KEYS):
        monkeypatch.delenv(key, raising=False)


def test_disabled_channels_are_activation_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)

    readiness = evaluate_top_up_production_readiness()

    assert readiness.activation_safe is True
    assert readiness.lemon_purchase_enabled is False
    assert readiness.local_purchase_enabled is False


def test_enabled_lemon_requires_complete_provider_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("MAESTRO_TOP_UP_PURCHASE_ENABLED", "true")

    readiness = evaluate_top_up_production_readiness()

    assert readiness.activation_safe is False
    assert "lemon_api_key_missing" in readiness.blockers
    assert "lemon_webhook_secret_weak" in readiness.blockers


def test_complete_lemon_configuration_is_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("MAESTRO_TOP_UP_PURCHASE_ENABLED", "true")
    monkeypatch.setenv("LEMONSQUEEZY_API_KEY", "api-key")
    monkeypatch.setenv("LEMONSQUEEZY_STORE_ID", "123")
    monkeypatch.setenv("LEMONSQUEEZY_TOP_UP_VARIANT_ID", "456")
    monkeypatch.setenv("LEMONSQUEEZY_WEBHOOK_SECRET", "x" * 40)
    monkeypatch.setenv("LEMONSQUEEZY_CHECKOUT_SUCCESS_URL", "https://app.example.com/console")

    readiness = require_top_up_production_readiness()

    assert readiness.activation_safe is True
    assert readiness.lemon_ready is True


def test_local_purchase_requires_admin_verification_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("MAESTRO_LOCAL_TUNISIA_TOP_UP_ENABLED", "true")
    monkeypatch.setenv("MAESTRO_TUNISIA_USD_TND_RATE", "3.1")
    monkeypatch.setenv("MAESTRO_TUNISIA_FX_SOURCE", "bank")
    monkeypatch.setenv("MAESTRO_TUNISIA_FX_REFERENCE", "rate-20260807")
    monkeypatch.setenv("MAESTRO_TUNISIA_FX_TTL_SECONDS", "3600")

    readiness = evaluate_top_up_production_readiness()

    assert readiness.activation_safe is False
    assert readiness.local_ready is True
    assert "tunisia_admin_verification_disabled" in readiness.blockers


def test_local_configuration_rejects_unbounded_fx_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("MAESTRO_LOCAL_TUNISIA_TOP_UP_ENABLED", "true")
    monkeypatch.setenv("MAESTRO_LOCAL_TUNISIA_TOP_UP_ADMIN_ENABLED", "true")
    monkeypatch.setenv("MAESTRO_TUNISIA_USD_TND_RATE", "3.1")
    monkeypatch.setenv("MAESTRO_TUNISIA_FX_SOURCE", "bank")
    monkeypatch.setenv("MAESTRO_TUNISIA_FX_REFERENCE", "rate-20260807")
    monkeypatch.setenv("MAESTRO_TUNISIA_FX_TTL_SECONDS", "999999")

    with pytest.raises(RuntimeError, match="production activation is blocked"):
        require_top_up_production_readiness()
