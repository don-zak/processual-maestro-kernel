from __future__ import annotations

import os

from processual_api.settings import settings

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})
_PRODUCTION = frozenset({"production", "prod"})


def durable_evaluation_authority_required() -> bool:
    app_env = os.environ.get("APP_ENV", settings.environment).strip().lower()
    runtime_env = os.environ.get("ENVIRONMENT", settings.environment).strip().lower()
    return settings.is_production or app_env in _PRODUCTION or runtime_env in _PRODUCTION


def durable_evaluation_authority_enabled() -> bool:
    if durable_evaluation_authority_required():
        return True

    explicit = os.environ.get("PMK_DURABLE_EVALUATION_AUTHORITY", "").strip().lower()
    if explicit in _TRUE:
        return True
    if explicit in _FALSE:
        return False

    database_url = os.environ.get("DATABASE_URL", "").strip().lower()
    return database_url.startswith(("postgresql://", "postgresql+asyncpg://"))


__all__ = [
    "durable_evaluation_authority_enabled",
    "durable_evaluation_authority_required",
]
