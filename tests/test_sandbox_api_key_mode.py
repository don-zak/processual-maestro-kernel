from __future__ import annotations

from types import SimpleNamespace

from processual_api.services import sandbox_api_key_mode as mode


def _settings(*, environment: str = "test", is_production: bool = False):
    return SimpleNamespace(environment=environment, is_production=is_production)


def test_explicit_false_is_allowed_only_outside_production(monkeypatch) -> None:
    monkeypatch.setattr(mode, "settings", _settings())
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql://qualification")
    monkeypatch.setenv("PMK_DURABLE_SANDBOX_API_KEYS", "false")

    assert mode.durable_sandbox_api_keys_required() is False
    assert mode.durable_sandbox_api_keys_enabled() is False


def test_app_env_production_overrides_explicit_false(monkeypatch) -> None:
    monkeypatch.setattr(mode, "settings", _settings())
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("PMK_DURABLE_SANDBOX_API_KEYS", "false")

    assert mode.durable_sandbox_api_keys_required() is True
    assert mode.durable_sandbox_api_keys_enabled() is True


def test_runtime_env_production_overrides_explicit_false(monkeypatch) -> None:
    monkeypatch.setattr(mode, "settings", _settings())
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("PMK_DURABLE_SANDBOX_API_KEYS", "false")

    assert mode.durable_sandbox_api_keys_required() is True
    assert mode.durable_sandbox_api_keys_enabled() is True


def test_settings_production_overrides_explicit_false(monkeypatch) -> None:
    monkeypatch.setattr(mode, "settings", _settings(is_production=True))
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("PMK_DURABLE_SANDBOX_API_KEYS", "false")

    assert mode.durable_sandbox_api_keys_required() is True
    assert mode.durable_sandbox_api_keys_enabled() is True


def test_postgresql_enables_durable_mode_by_default(monkeypatch) -> None:
    monkeypatch.setattr(mode, "settings", _settings())
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.delenv("PMK_DURABLE_SANDBOX_API_KEYS", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://qualification")

    assert mode.durable_sandbox_api_keys_enabled() is True
