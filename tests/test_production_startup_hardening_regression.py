from __future__ import annotations

import importlib

import pytest


def _api_settings_class(monkeypatch):
    """Import APISettings safely without depending on module-level weak defaults."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("JWT_SECRET", "dev-test-jwt-secret-with-enough-length")
    monkeypatch.setenv("API_KEYS", "pmk_dev_test_key_with_enough_length")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://pmk_user:dev_test_password@localhost:5432/processual_maestro",
    )
    monkeypatch.setenv("REDIS_URL", "redis://:dev_test_redis_password@localhost:6379/0")
    monkeypatch.setenv("POSTGRES_PASSWORD", "dev-test-postgres-password")
    monkeypatch.setenv("REDIS_PASSWORD", "dev-test-redis-password")
    monkeypatch.setenv("GRAFANA_ADMIN_PASSWORD", "dev-test-grafana-password")

    module = importlib.import_module("processual_api.settings")
    return module.APISettings


def _set_strong_production_env(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("API_DEBUG", "true")
    monkeypatch.setenv("JWT_SECRET", "prod-test-jwt-secret-with-enough-length-and-entropy")
    monkeypatch.setenv("API_KEYS", "pmk_bootstrap_test_key_with_enough_length_and_entropy")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://pmk_user:prod_test_password@postgres:5432/processual_maestro",
    )
    monkeypatch.setenv("REDIS_URL", "redis://:prod_test_redis_password@redis:6379/0")
    monkeypatch.setenv("POSTGRES_PASSWORD", "prod-test-postgres-password")
    monkeypatch.setenv("REDIS_PASSWORD", "prod-test-redis-password")
    monkeypatch.setenv("GRAFANA_ADMIN_PASSWORD", "prod-test-grafana-password")
    monkeypatch.setenv("CORS_ORIGINS", "https://console.example.com")
    monkeypatch.setenv(
        "PROCESSUAL_CRYPTO_KEY_B64",
        "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
    )


@pytest.mark.parametrize(
    ("env_name", "env_value", "message"),
    [
        ("JWT_SECRET", "CHANGE_ME_IN_PRODUCTION", "JWT_SECRET"),
        ("JWT_SECRET", "", "JWT_SECRET"),
        ("API_KEYS", "admin", "API_KEYS"),
        ("API_KEYS", "", "API_KEYS"),
        ("DATABASE_URL", "", "DATABASE_URL"),
        ("REDIS_URL", "", "REDIS_URL"),
        ("POSTGRES_PASSWORD", "password", "POSTGRES_PASSWORD"),
        ("REDIS_PASSWORD", "password", "REDIS_PASSWORD"),
        ("GRAFANA_ADMIN_PASSWORD", "admin", "GRAFANA_ADMIN_PASSWORD"),
        ("CORS_ORIGINS", "*", "CORS_ORIGINS"),
    ],
)
def test_production_rejects_weak_startup_settings(monkeypatch, env_name, env_value, message):
    APISettings = _api_settings_class(monkeypatch)
    _set_strong_production_env(monkeypatch)
    monkeypatch.setenv(env_name, env_value)

    with pytest.raises(RuntimeError, match=message):
        APISettings()


def test_production_accepts_strong_settings_and_forces_debug_false(monkeypatch):
    APISettings = _api_settings_class(monkeypatch)
    _set_strong_production_env(monkeypatch)

    settings = APISettings()

    assert settings.is_production is True
    assert settings.debug is False
    assert settings.cors_origins == ["https://console.example.com"]


def test_non_production_can_enable_debug_with_strong_local_settings(monkeypatch):
    APISettings = _api_settings_class(monkeypatch)

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("API_DEBUG", "true")
    monkeypatch.setenv("CORS_ORIGINS", "*")

    settings = APISettings()

    assert settings.is_production is False
    assert settings.debug is True
    assert settings.cors_origins == ["*"]