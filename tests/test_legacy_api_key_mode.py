from __future__ import annotations

from types import SimpleNamespace

from processual_api.services import legacy_api_key_mode as mode


def _settings(*, environment: str = "test", is_production: bool = False):
    return SimpleNamespace(environment=environment, is_production=is_production)


def test_nonproduction_defaults_to_transition_authority(monkeypatch) -> None:
    monkeypatch.setattr(mode, "settings", _settings())
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.delenv("PMK_LEGACY_DYNAMIC_API_KEYS", raising=False)

    assert mode.production_legacy_api_key_cutover_enforced() is False
    assert mode.legacy_dynamic_api_key_authority_enabled() is True


def test_nonproduction_can_explicitly_disable_legacy_authority(monkeypatch) -> None:
    monkeypatch.setattr(mode, "settings", _settings())
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("PMK_LEGACY_DYNAMIC_API_KEYS", "false")

    assert mode.legacy_dynamic_api_key_authority_enabled() is False


def test_production_app_env_forces_legacy_authority_off(monkeypatch) -> None:
    monkeypatch.setattr(mode, "settings", _settings())
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("PMK_LEGACY_DYNAMIC_API_KEYS", "true")

    assert mode.production_legacy_api_key_cutover_enforced() is True
    assert mode.legacy_dynamic_api_key_authority_enabled() is False


def test_production_runtime_env_forces_legacy_authority_off(monkeypatch) -> None:
    monkeypatch.setattr(mode, "settings", _settings(environment="development"))
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("PMK_LEGACY_DYNAMIC_API_KEYS", "true")

    assert mode.legacy_dynamic_api_key_authority_enabled() is False


def test_settings_production_forces_legacy_authority_off(monkeypatch) -> None:
    monkeypatch.setattr(mode, "settings", _settings(is_production=True))
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("PMK_LEGACY_DYNAMIC_API_KEYS", "true")

    assert mode.legacy_dynamic_api_key_authority_enabled() is False
