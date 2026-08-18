from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

EXPECTED_ALEMBIC_HEAD = "20260818_0050"
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
)


@dataclass(frozen=True, slots=True)
class ReleaseGateResult:
    environment: str
    expected_alembic_head: str
    checks: tuple[str, ...]


def _required(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"release gate: {name} is required")
    lowered = value.lower()
    if any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
        raise RuntimeError(f"release gate: {name} still contains a placeholder")
    return value


def _require_https(value: str, name: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError(f"release gate: {name} must use an absolute HTTPS URL")


def evaluate_release_environment(
    environ: Mapping[str, str] | None = None,
) -> ReleaseGateResult:
    values = os.environ if environ is None else environ
    environment = values.get("ENVIRONMENT", "").strip().lower()
    if environment not in ALLOWED_RELEASE_ENVIRONMENTS:
        raise RuntimeError("release gate: ENVIRONMENT must be staging or production")

    checks: list[str] = []
    resolved = {name: _required(values, name) for name in _REQUIRED_VALUES}
    checks.append("required_values")

    if len(resolved["JWT_SECRET"]) < 32:
        raise RuntimeError("release gate: JWT_SECRET must be at least 32 characters")
    if len(resolved["LEMONSQUEEZY_WEBHOOK_SECRET"]) < 32:
        raise RuntimeError(
            "release gate: LEMONSQUEEZY_WEBHOOK_SECRET must be at least 32 characters"
        )
    if not resolved["LEMONSQUEEZY_STORE_ID"].isdigit() or int(
        resolved["LEMONSQUEEZY_STORE_ID"]
    ) <= 0:
        raise RuntimeError("release gate: LEMONSQUEEZY_STORE_ID must be positive")
    checks.append("secret_strength")

    cors_origins = [
        item.strip() for item in values.get("CORS_ORIGINS", "").split(",") if item.strip()
    ]
    if not cors_origins or "*" in cors_origins:
        raise RuntimeError("release gate: CORS_ORIGINS must be explicit")
    for origin in cors_origins:
        _require_https(origin, "CORS_ORIGINS")
    checks.append("cors")

    for name in (
        "AUTH_DELIVERY_PROVIDER_URL",
        "AUTH_PUBLIC_BASE_URL",
        "LEMONSQUEEZY_CHECKOUT_SUCCESS_URL",
        "LEMONSQUEEZY_CHECKOUT_CANCEL_URL",
    ):
        _require_https(resolved[name], name)
    checks.append("public_urls")

    database_url = urlparse(resolved["DATABASE_URL"])
    if database_url.scheme not in {"postgresql", "postgresql+asyncpg"}:
        raise RuntimeError("release gate: DATABASE_URL must use PostgreSQL")
    redis_url = urlparse(resolved["REDIS_URL"])
    if redis_url.scheme not in {"redis", "rediss"}:
        raise RuntimeError("release gate: REDIS_URL must use Redis")
    checks.append("datastores")

    if values.get("API_DEBUG", "false").strip().lower() not in {"false", "0", "no"}:
        raise RuntimeError("release gate: API_DEBUG must be disabled")
    if values.get("AUDIT_ENABLED", "true").strip().lower() != "true":
        raise RuntimeError("release gate: AUDIT_ENABLED must be true")
    if values.get("RATE_LIMIT_ENABLED", "true").strip().lower() != "true":
        raise RuntimeError("release gate: RATE_LIMIT_ENABLED must be true")
    checks.append("runtime_controls")

    if resolved["MIGRATION_BACKUP_REFERENCE"] == resolved[
        "MIGRATION_RESTORE_REHEARSAL_REFERENCE"
    ]:
        raise RuntimeError(
            "release gate: migration backup and restore rehearsal references must differ"
        )
    checks.append("migration_rehearsal_evidence")

    return ReleaseGateResult(
        environment=environment,
        expected_alembic_head=EXPECTED_ALEMBIC_HEAD,
        checks=tuple(checks),
    )


def main() -> int:
    try:
        result = evaluate_release_environment()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        "release gate passed: "
        f"environment={result.environment} "
        f"alembic_head={result.expected_alembic_head} "
        f"checks={','.join(result.checks)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
