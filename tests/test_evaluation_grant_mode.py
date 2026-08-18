from __future__ import annotations

from processual_api.services import evaluation_grant_mode as mode


def test_explicit_false_allowed_outside_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql://qualification")
    monkeypatch.setenv("PMK_DURABLE_EVALUATION_AUTHORITY", "false")
    monkeypatch.setattr(mode.settings, "is_production", False)

    assert mode.durable_evaluation_authority_required() is False
    assert mode.durable_evaluation_authority_enabled() is False


def test_production_forces_durable_even_when_flag_false(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("PMK_DURABLE_EVALUATION_AUTHORITY", "false")
    monkeypatch.setattr(mode.settings, "is_production", False)

    assert mode.durable_evaluation_authority_required() is True
    assert mode.durable_evaluation_authority_enabled() is True


def test_postgres_enables_durable_by_default(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql://qualification")
    monkeypatch.delenv("PMK_DURABLE_EVALUATION_AUTHORITY", raising=False)
    monkeypatch.setattr(mode.settings, "is_production", False)

    assert mode.durable_evaluation_authority_enabled() is True


def test_non_postgres_local_defaults_to_legacy_transition(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///local.db")
    monkeypatch.delenv("PMK_DURABLE_EVALUATION_AUTHORITY", raising=False)
    monkeypatch.setattr(mode.settings, "is_production", False)

    assert mode.durable_evaluation_authority_enabled() is False
