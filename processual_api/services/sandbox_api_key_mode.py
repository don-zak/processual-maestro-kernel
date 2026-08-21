from __future__ import annotations

import os

from processual_api.settings import settings

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})
_PRODUCTION = frozenset({"production", "prod"})


def durable_sandbox_api_keys_required() -> bool:
    """Return whether the current runtime must use durable sandbox authority."""

    app_env = os.environ.get("APP_ENV", settings.environment).strip().lower()
    runtime_env = os.environ.get("ENVIRONMENT", settings.environment).strip().lower()
    return settings.is_production or app_env in _PRODUCTION or runtime_env in _PRODUCTION


def durable_sandbox_api_keys_enabled() -> bool:
    """Return the authoritative durable-mode decision.

    Production can never opt out. Outside production, an explicit environment
    switch may enable/disable the transition; otherwise a PostgreSQL database
    configuration enables durable authority automatically.
    """

    if durable_sandbox_api_keys_required():
        return True

    explicit = os.environ.get("PMK_DURABLE_SANDBOX_API_KEYS", "").strip().lower()
    if explicit in _TRUE:
        return True
    if explicit in _FALSE:
        return False

    database_url = os.environ.get("DATABASE_URL", "").strip().lower()
    return database_url.startswith(("postgresql://", "postgresql+asyncpg://"))


__all__ = [
    "durable_sandbox_api_keys_enabled",
    "durable_sandbox_api_keys_required",
]
