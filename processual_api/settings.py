from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field


@dataclass
class APISettings:
    title: str = "Processual Maestro Kernel API"
    version: str = "2.0.0"
    description: str = "Backend API for CGT v2 evaluation, workflow governance, observability, and monitoring."
    host: str = field(default_factory=lambda: os.environ.get("API_HOST", "0.0.0.0"))  # nosec
    port: int = field(default_factory=lambda: int(os.environ.get("API_PORT", "8000")))
    log_level: str = field(default_factory=lambda: os.environ.get("API_LOG_LEVEL", "info"))
    debug: bool = False

    # --- Observability ---
    sentry_dsn: str | None = field(default_factory=lambda: os.environ.get("SENTRY_DSN"))
    sentry_environment: str = field(default_factory=lambda: os.environ.get("SENTRY_ENVIRONMENT", "development"))
    sentry_traces_sample_rate: float = field(
        default_factory=lambda: float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
    )

    # --- CORS ---
    cors_origins: list[str] = field(
        default_factory=lambda: os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
    )

    # --- JWT Authentication ---
    jwt_secret: str = field(default_factory=lambda: os.environ.get("JWT_SECRET", "CHANGE_ME_IN_PRODUCTION"))
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = field(default_factory=lambda: int(os.environ.get("JWT_EXPIRE_MINUTES", "60")))

    # --- API Key Authentication ---
    api_keys: list[str] = field(
        default_factory=lambda: os.environ.get("API_KEYS", "").split(",") if os.environ.get("API_KEYS") else []
    )

    # --- Database (PostgreSQL) ---
    database_url: str | None = field(default_factory=lambda: os.environ.get("DATABASE_URL"))
    database_pool_min: int = field(default_factory=lambda: int(os.environ.get("DATABASE_POOL_MIN", "2")))
    database_pool_max: int = field(default_factory=lambda: int(os.environ.get("DATABASE_POOL_MAX", "10")))

    # --- Cache (Redis) ---
    redis_url: str | None = field(default_factory=lambda: os.environ.get("REDIS_URL"))
    redis_rate_limit_prefix: str = "rl:"

    # --- Rate Limiting ---
    rate_limit_enabled: bool = field(
        default_factory=lambda: os.environ.get("RATE_LIMIT_ENABLED", "true").lower() == "true"
    )
    rate_limit_default: str = field(default_factory=lambda: os.environ.get("RATE_LIMIT_DEFAULT", "100/minute"))
    rate_limit_authenticated: str = field(
        default_factory=lambda: os.environ.get("RATE_LIMIT_AUTHENTICATED", "500/minute")
    )

    # --- Audit ---
    audit_enabled: bool = field(default_factory=lambda: os.environ.get("AUDIT_ENABLED", "true").lower() == "true")

    # --- Environment ---
    environment: str = field(default_factory=lambda: os.environ.get("ENVIRONMENT", "development"))

    _WEAK_SECRETS = {
        "",
        "change_me",
        "admin",
        "password",
        "processual",
        "test",
        "dev",
        "changeme",
        "default",
        "secret",
        "123456",
    }

    def _reject_weak(self, field_name: str, value: str | None, label: str) -> None:
        if not value or value.strip().lower() in self._WEAK_SECRETS:
            detail = (
                f"{label} is missing or set to a weak value. "
                f"Set a strong, unique {field_name} environment variable "
                "before deploying to production."
            )
            if self.is_production:
                raise RuntimeError(detail)
            warnings.warn(detail, stacklevel=2)

    def _reject_wildcard_cors(self) -> None:
        if self.is_production and any(o.strip() == "*" for o in self.cors_origins):
            raise RuntimeError(
                "CORS_ORIGINS contains wildcard '*' in production. "
                "Set explicit allowed origins for production deployments."
            )

    def __post_init__(self) -> None:
        if self.is_production:
            self.debug = False
        else:
            self.debug = os.environ.get("API_DEBUG", "false").lower() == "true"

        if self.jwt_secret == "CHANGE_ME_IN_PRODUCTION" or not self.jwt_secret:
            msg = (
                "JWT_SECRET is still set to the insecure default 'CHANGE_ME_IN_PRODUCTION'. "
                if self.jwt_secret == "CHANGE_ME_IN_PRODUCTION"
                else "JWT_SECRET is empty. "
            )
            detail = msg + "Set a strong, unique JWT_SECRET environment variable before deploying to production."
            if self.is_production:
                raise RuntimeError(detail)
            warnings.warn(detail, stacklevel=2)

        self._reject_weak("JWT_SECRET", self.jwt_secret, "JWT_SECRET")
        self._reject_wildcard_cors()

        api_keys_str = ",".join(self.api_keys) if self.api_keys else ""
        self._reject_weak("API_KEYS", api_keys_str if api_keys_str else None, "API_KEYS")
        self._reject_weak("DATABASE_URL", self.database_url, "DATABASE_URL")
        self._reject_weak("REDIS_URL", self.redis_url, "REDIS_URL")

        pg_pw = os.environ.get("POSTGRES_PASSWORD")
        self._reject_weak("POSTGRES_PASSWORD", pg_pw, "POSTGRES_PASSWORD")
        redis_pw = os.environ.get("REDIS_PASSWORD")
        self._reject_weak("REDIS_PASSWORD", redis_pw, "REDIS_PASSWORD")
        gf_pw = os.environ.get("GRAFANA_ADMIN_PASSWORD")
        self._reject_weak("GRAFANA_ADMIN_PASSWORD", gf_pw, "GRAFANA_ADMIN_PASSWORD")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = APISettings()
