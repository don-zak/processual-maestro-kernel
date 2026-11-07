from __future__ import annotations

import warnings

from processual_api.settings import APISettings


def _managed_runtime_environment(monkeypatch, *, production: bool) -> None:
    values = {
        "ENVIRONMENT": "production" if production else "development",
        "JWT_SECRET": "j" * 48,
        "API_KEYS": "service-key-" + "a" * 32,
        "DATABASE_URL": "postgresql+asyncpg://app:strong-password@db:5432/app",
        "REDIS_URL": "rediss://:strong-password@redis:6379/0",
        "MAESTRO_ADMIN_EMAIL": "admin@maestro.invalid",
        "MAESTRO_ADMIN_PASSWORD": "m" * 40,
        "CORS_ORIGINS": "https://app.maestro.invalid",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    for name in ("POSTGRES_PASSWORD", "REDIS_PASSWORD", "GRAFANA_ADMIN_PASSWORD"):
        monkeypatch.delenv(name, raising=False)


def test_managed_runtime_does_not_warn_for_component_only_secrets(monkeypatch) -> None:
    _managed_runtime_environment(monkeypatch, production=False)

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        APISettings()

    messages = [str(item.message) for item in captured]
    assert not any("POSTGRES_PASSWORD" in message for message in messages)
    assert not any("REDIS_PASSWORD" in message for message in messages)
    assert not any("GRAFANA_ADMIN_PASSWORD" in message for message in messages)


def test_production_managed_runtime_does_not_require_component_only_secrets(monkeypatch) -> None:
    _managed_runtime_environment(monkeypatch, production=True)

    settings = APISettings()

    assert settings.is_production is True
    assert settings.database_url is not None
    assert settings.redis_url is not None
