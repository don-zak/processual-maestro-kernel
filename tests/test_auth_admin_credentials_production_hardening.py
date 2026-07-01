from __future__ import annotations

import asyncio
import importlib

import pytest
from fastapi import HTTPException

from processual_api.settings import APISettings

auth_router = importlib.import_module("processual_api.auth.router")

STRONG_PRODUCTION_ENV = {
    "ENVIRONMENT": "production",
    "APP_ENV": "production",
    "JWT_SECRET": "strong-production-jwt-secret-value-123456789",
    "API_KEYS": "pmk_bootstrap_strong_random_service_key_123456789",
    "DATABASE_URL": (
        "postgresql+asyncpg://pmk_user:"
        "strong_unique_postgres_secret@db:5432/processual_maestro"
    ),
    "REDIS_URL": "redis://:strong_unique_redis_secret@redis:6379/0",
    "POSTGRES_PASSWORD": "strong_unique_postgres_secret",
    "REDIS_PASSWORD": "strong_unique_redis_secret",
    "GRAFANA_ADMIN_PASSWORD": "strong_unique_grafana_secret",
    "CORS_ORIGINS": "https://console.example.com",
    "PROCESSUAL_CRYPTO_KEY_B64": (
        "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
    ),
}


def _apply_strong_production_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in STRONG_PRODUCTION_ENV.items():
        monkeypatch.setenv(key, value)


def test_production_requires_maestro_admin_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _apply_strong_production_env(monkeypatch)
    monkeypatch.delenv("MAESTRO_ADMIN_EMAIL", raising=False)
    monkeypatch.setenv(
        "MAESTRO_ADMIN_PASSWORD",
        "strong_unique_maestro_admin_password",
    )

    with pytest.raises(RuntimeError, match="MAESTRO_ADMIN_EMAIL"):
        APISettings()


def test_production_requires_maestro_admin_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _apply_strong_production_env(monkeypatch)
    monkeypatch.setenv("MAESTRO_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.delenv("MAESTRO_ADMIN_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="MAESTRO_ADMIN_EMAIL"):
        APISettings()


def test_production_rejects_weak_maestro_admin_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _apply_strong_production_env(monkeypatch)
    monkeypatch.setenv("MAESTRO_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("MAESTRO_ADMIN_PASSWORD", "admin")

    with pytest.raises(RuntimeError, match="MAESTRO_ADMIN_PASSWORD"):
        APISettings()


def test_production_accepts_strong_maestro_admin_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _apply_strong_production_env(monkeypatch)
    monkeypatch.setenv("MAESTRO_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv(
        "MAESTRO_ADMIN_PASSWORD",
        "strong_unique_maestro_admin_password",
    )

    settings = APISettings()

    assert settings.is_production is True
    assert settings.maestro_admin_email == "admin@example.com"
    assert settings.maestro_admin_password == (
        "strong_unique_maestro_admin_password"
    )


def test_auth_token_does_not_derive_production_credentials_from_jwt_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSettings:
        maestro_admin_email = ""
        maestro_admin_password = ""
        is_production = True
        jwt_secret = "abcdefgh-strong-production-secret-ZZZZZZZZ"

    monkeypatch.setattr(auth_router, "settings", FakeSettings())

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            auth_router.login_for_access_token(
                auth_router.LoginRequest(
                    username="abcdefgh",
                    password="ZZZZZZZZ",
                    role="admin",
                )
            )
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Admin credentials are not configured"
