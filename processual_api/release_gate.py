from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

EXPECTED_ALEMBIC_HEAD = "20260818_0054"
ALLOWED_RELEASE_ENVIRONMENTS = {"staging", "production"}
_PLACEHOLDER_MARKERS = (
    "replace_with",
    "change_me",
    "changeme",
    "example.com",
    "your-frontend",
    "yourdomain",
)
_REQUIRED_VALUES = (
    "JWT_SECRET",
    "API_KEYS",
    "PROCESSUAL_CRYPTO_KEY_B64",
    "DATABASE_URL",
    "REDIS_URL",
    "MAESTRO_ADMIN_EMAIL",
    "MAESTRO_ADMIN_PASSWORD",
    "POSTGRES_PASSWORD",
    "REDIS_PASSWORD",
    "GRAFANA_ADMIN_PASSWORD",
    "AUTH_TOKEN_PEPPER",
    "AUTH_RATE_LIMIT_PEPPER",
    "AUTH_DELIVERY_KEY_RING_JSON",
    "AUTH_DELIVERY_CURRENT_KEY_VERSION",
    "AUTH_DELIVERY_PROVIDER_URL",
    "AUTH_DELIVERY_PROVIDER_TOKEN",
    "AUTH_PUBLIC_BASE_URL",
    "AUTH_MFA_KEY_RING_JSON",
    "AUTH_MFA_CURRENT_KEY_VERSION",
    "ADMIN_MARKETPLACE_PAYMENT_DESTINATION_KEY_RING_JSON",
    "ADMIN_MARKETPLACE_PAYMENT_DESTINATION_CURRENT_KEY_VERSION",
    "LEMONSQUEEZY_API_KEY",
    "LEMONSQUEEZY_STORE_ID",
    "LEMONSQUEEZY_WEBHOOK_SECRET",
    "LEMONSQUEEZY_CHECKOUT_SUCCESS_URL",
    "LEMONSQUEEZY_CHECKOUT_CANCEL_URL",
    "MIGRATION_BACKUP_REFERENCE",
    "MIGRATION_RESTORE_REHEARSAL_REFERENCE",
    "CORS_ORIGINS",
)


@dataclass(frozen=True, slots=True)
class ReleaseGateResult:
    environment: str
    expected_alembic_head: str
    checks: tuple[str, ...]


def _required_value(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise RuntimeError(f"release gate: missing required release value: {name}")
    return value


def _reject_placeholder(name: str, value: str) -> None:
    normalized = value.lower()
    if any(marker in normalized for marker in _PLACEHOLDER_MARKERS):
        raise RuntimeError(f"release gate: release value {name} contains a placeholder marker")


def _require_secret_strength(name: str, value: str, *, minimum: int = 32) -> None:
    _reject_placeholder(name, value)
    if len(value) < minimum:
        raise RuntimeError(f"release gate: release secret {name} is too short")


def _require_https_url(name: str, value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError(f"release gate: release URL {name} must be HTTPS")
    _reject_placeholder(name, value)


def evaluate_release_environment(
    environment: Mapping[str, str] | None = None,
) -> ReleaseGateResult:
    values = os.environ if environment is None else environment
    release_environment = _required_value(values, "ENVIRONMENT").lower()
    if release_environment not in ALLOWED_RELEASE_ENVIRONMENTS:
        raise RuntimeError("release gate: only staging or production is permitted")

    required = {name: _required_value(values, name) for name in _REQUIRED_VALUES}

    for name in (
        "JWT_SECRET",
        "API_KEYS",
        "PROCESSUAL_CRYPTO_KEY_B64",
        "MAESTRO_ADMIN_PASSWORD",
        "POSTGRES_PASSWORD",
        "REDIS_PASSWORD",
        "GRAFANA_ADMIN_PASSWORD",
        "AUTH_TOKEN_PEPPER",
        "AUTH_RATE_LIMIT_PEPPER",
        "AUTH_DELIVERY_PROVIDER_TOKEN",
        "LEMONSQUEEZY_API_KEY",
        "LEMONSQUEEZY_WEBHOOK_SECRET",
    ):
        _require_secret_strength(name, required[name])

    store_id = required["LEMONSQUEEZY_STORE_ID"]
    if not store_id.isdigit() or int(store_id) <= 0:
        raise RuntimeError("release gate: LEMONSQUEEZY_STORE_ID must be a positive integer")

    cors_origins = tuple(
        value.strip() for value in required["CORS_ORIGINS"].split(",") if value.strip()
    )
    if not cors_origins:
        raise RuntimeError("release gate: CORS_ORIGINS must contain at least one origin")
    for origin in cors_origins:
        _require_https_url("CORS_ORIGINS", origin)

    for name in (
        "AUTH_DELIVERY_PROVIDER_URL",
        "AUTH_PUBLIC_BASE_URL",
        "LEMONSQUEEZY_CHECKOUT_SUCCESS_URL",
        "LEMONSQUEEZY_CHECKOUT_CANCEL_URL",
    ):
        _require_https_url(name, required[name])

    database_url = urlparse(required["DATABASE_URL"])
    if database_url.scheme not in {"postgresql", "postgresql+asyncpg"}:
        raise RuntimeError("release gate: DATABASE_URL must use PostgreSQL")
    redis_url = urlparse(required["REDIS_URL"])
    if redis_url.scheme not in {"redis", "rediss"}:
        raise RuntimeError("release gate: REDIS_URL must use Redis")

    if values.get("API_DEBUG", "").strip().lower() != "false":
        raise RuntimeError("release gate: API_DEBUG must be false")
    if values.get("AUDIT_ENABLED", "").strip().lower() != "true":
        raise RuntimeError("release gate: AUDIT_ENABLED must be true")
    if values.get("RATE_LIMIT_ENABLED", "").strip().lower() != "true":
        raise RuntimeError("release gate: RATE_LIMIT_ENABLED must be true")

    backup_reference = required["MIGRATION_BACKUP_REFERENCE"]
    restore_reference = required["MIGRATION_RESTORE_REHEARSAL_REFERENCE"]
    _reject_placeholder("MIGRATION_BACKUP_REFERENCE", backup_reference)
    _reject_placeholder("MIGRATION_RESTORE_REHEARSAL_REFERENCE", restore_reference)
    if backup_reference == restore_reference:
        raise RuntimeError(
            "release gate: migration backup and restore rehearsal references must differ"
        )

    return ReleaseGateResult(
        environment=release_environment,
        expected_alembic_head=EXPECTED_ALEMBIC_HEAD,
        checks=(
            "required_values",
            "secret_strength",
            "cors",
            "public_urls",
            "datastores",
            "runtime_controls",
            "migration_rehearsal_evidence",
        ),
    )


def main() -> int:
    try:
        result = evaluate_release_environment()
    except RuntimeError as exc:
        print(f"commercial-release-gate: FAIL: {exc}", file=sys.stderr)
        return 1

    print(
        "commercial-release-gate: PASS "
        f"environment={result.environment} alembic_head={result.expected_alembic_head}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
