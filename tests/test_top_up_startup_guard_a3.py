from __future__ import annotations

import pytest

from processual_api.admin_marketplace.top_up_operations_router import (
    _enforce_production_readiness_on_import,
)
from processual_api.settings import settings


TOP_UP_KEYS = (
    "MAESTRO_TOP_UP_PURCHASE_ENABLED",
    "MAESTRO_LOCAL_TUNISIA_TOP_UP_ENABLED",
    "MAESTRO_LOCAL_TUNISIA_TOP_UP_ADMIN_ENABLED",
    "LEMONSQUEEZY_API_KEY",
    "LEMONSQUEEZY_STORE_ID",
    "LEMONSQUEEZY_TOP_UP_VARIANT_ID",
    "LEMONSQUEEZY_WEBHOOK_SECRET",
    "LEMONSQUEEZY_CHECKOUT_SUCCESS_URL",
    "MAESTRO_TUNISIA_USD_TND_RATE",
    "MAESTRO_TUNISIA_FX_SOURCE",
    "MAESTRO_TUNISIA_FX_REFERENCE",
    "MAESTRO_TUNISIA_FX_TTL_SECONDS",
)


def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in TOP_UP_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_development_startup_does_not_require_commercial_activation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear(monkeypatch)
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setenv("MAESTRO_TOP_UP_PURCHASE_ENABLED", "true")

    _enforce_production_readiness_on_import()


def test_production_startup_allows_all_channels_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear(monkeypatch)
    monkeypatch.setattr(settings, "environment", "production")

    _enforce_production_readiness_on_import()


def test_production_startup_blocks_incomplete_enabled_lemon_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear(monkeypatch)
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setenv("MAESTRO_TOP_UP_PURCHASE_ENABLED", "true")

    with pytest.raises(RuntimeError, match="production activation is blocked"):
        _enforce_production_readiness_on_import()


def test_production_startup_accepts_complete_enabled_lemon_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear(monkeypatch)
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setenv("MAESTRO_TOP_UP_PURCHASE_ENABLED", "true")
    monkeypatch.setenv("LEMONSQUEEZY_API_KEY", "api-key")
    monkeypatch.setenv("LEMONSQUEEZY_STORE_ID", "123")
    monkeypatch.setenv("LEMONSQUEEZY_TOP_UP_VARIANT_ID", "456")
    monkeypatch.setenv("LEMONSQUEEZY_WEBHOOK_SECRET", "x" * 40)
    monkeypatch.setenv(
        "LEMONSQUEEZY_CHECKOUT_SUCCESS_URL",
        "https://app.example.com/console",
    )

    _enforce_production_readiness_on_import()
