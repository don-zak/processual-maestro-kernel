from __future__ import annotations

import os

from processual_api.settings import settings

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})
_PRODUCTION = frozenset({"production", "prod"})


def production_legacy_api_key_cutover_enforced() -> bool:
    app_env = os.environ.get("APP_ENV", settings.environment).strip().lower()
    runtime_env = os.environ.get("ENVIRONMENT", settings.environment).strip().lower()
    return settings.is_production or app_env in _PRODUCTION or runtime_env in _PRODUCTION


def legacy_dynamic_api_key_authority_enabled() -> bool:
    """Return whether Settings-JSON dynamic API keys may be authoritative.

    Production is permanently fail-closed. The flag exists only to make the
    non-production migration window explicit and testable; it cannot reopen
    legacy authority once a process identifies itself as production.
    """

    if production_legacy_api_key_cutover_enforced():
        return False

    explicit = os.environ.get("PMK_LEGACY_DYNAMIC_API_KEYS", "").strip().lower()
    if explicit in _TRUE:
        return True
    if explicit in _FALSE:
        return False

    return True


__all__ = [
    "legacy_dynamic_api_key_authority_enabled",
    "production_legacy_api_key_cutover_enforced",
]
