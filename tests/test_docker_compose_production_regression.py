from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.yml"
DOCKERFILE = ROOT / "Dockerfile"
ENV_TEMPLATE = ROOT / ".env.production.example"
DEPLOYMENT_DOCS = ROOT / "DEPLOYMENT_EXTERNAL.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_contains_all(text: str, markers: list[str], label: str) -> None:
    missing = [marker for marker in markers if marker not in text]
    assert not missing, f"Missing {label} markers: {missing}"


def test_docker_compose_api_service_keeps_production_hardening_markers():
    text = read(COMPOSE)

    required = [
        "processual-maestro-api",
        "ENVIRONMENT=production",
        "CORS_ORIGINS=${CORS_ORIGINS:?CORS_ORIGINS is required}",
        "PROCESSUAL_CRYPTO_KEY_B64=${PROCESSUAL_CRYPTO_KEY_B64:?PROCESSUAL_CRYPTO_KEY_B64 is required}",
        "JWT_SECRET=${JWT_SECRET:?JWT_SECRET is required}",
        "API_KEYS=${API_KEYS:?API_KEYS is required}",
        "DATABASE_URL=${DATABASE_URL:?DATABASE_URL is required}",
        "POSTGRES_PASSWORD=${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}",
        "REDIS_URL=${REDIS_URL:-redis://:${REDIS_PASSWORD:?REDIS_PASSWORD is required}@redis:6379/0}",
        "REDIS_PASSWORD=${REDIS_PASSWORD:?REDIS_PASSWORD is required}",
        "GRAFANA_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:?GRAFANA_ADMIN_PASSWORD is required}",
        "MAESTRO_ADMIN_EMAIL=${MAESTRO_ADMIN_EMAIL:?MAESTRO_ADMIN_EMAIL is required}",
        "MAESTRO_ADMIN_PASSWORD=${MAESTRO_ADMIN_PASSWORD:?MAESTRO_ADMIN_PASSWORD is required}",
        "AUTH_TOKEN_PEPPER=${AUTH_TOKEN_PEPPER:?AUTH_TOKEN_PEPPER is required}",
        "AUTH_RATE_LIMIT_PEPPER=${AUTH_RATE_LIMIT_PEPPER:?AUTH_RATE_LIMIT_PEPPER is required}",
        "AUTH_DELIVERY_KEY_RING_JSON=${AUTH_DELIVERY_KEY_RING_JSON:?AUTH_DELIVERY_KEY_RING_JSON is required}",
        "AUTH_DELIVERY_CURRENT_KEY_VERSION=${AUTH_DELIVERY_CURRENT_KEY_VERSION:?AUTH_DELIVERY_CURRENT_KEY_VERSION is required}",
        "AUTH_PUBLIC_BASE_URL=${AUTH_PUBLIC_BASE_URL:?AUTH_PUBLIC_BASE_URL is required}",
        "AUTH_MFA_KEY_RING_JSON=${AUTH_MFA_KEY_RING_JSON:?AUTH_MFA_KEY_RING_JSON is required}",
        "AUTH_MFA_CURRENT_KEY_VERSION=${AUTH_MFA_CURRENT_KEY_VERSION:?AUTH_MFA_CURRENT_KEY_VERSION is required}",
        "ADMIN_MARKETPLACE_PAYMENT_DESTINATION_KEY_RING_JSON=${ADMIN_MARKETPLACE_PAYMENT_DESTINATION_KEY_RING_JSON:?ADMIN_MARKETPLACE_PAYMENT_DESTINATION_KEY_RING_JSON is required}",
        "ADMIN_MARKETPLACE_PAYMENT_DESTINATION_CURRENT_KEY_VERSION=${ADMIN_MARKETPLACE_PAYMENT_DESTINATION_CURRENT_KEY_VERSION:?ADMIN_MARKETPLACE_PAYMENT_DESTINATION_CURRENT_KEY_VERSION is required}",
        "RATE_LIMIT_ENABLED=true",
        "AUDIT_ENABLED=true",
        "read_only: true",
        "no-new-privileges:true",
        'test: ["CMD", "curl", "-f", "http://localhost:8000/health/live"]',
        "condition: service_healthy",
    ]

    assert_contains_all(text, required, "docker compose API production hardening")


def test_docker_compose_uses_explicit_public_build_target_for_external_profile():
    text = read(COMPOSE)

    required = [
        "build:",
        "context: .",
        "target: public",
    ]

    assert_contains_all(text, required, "docker compose public build target")


def test_docker_compose_dependency_services_keep_passwords_healthchecks_and_network_boundary():
    text = read(COMPOSE)

    required = [
        "redis:7-alpine",
        'command: ["redis-server", "--requirepass", "${REDIS_PASSWORD:?REDIS_PASSWORD is required}"]',
        "REDISCLI_AUTH=${REDIS_PASSWORD:?REDIS_PASSWORD is required}",
        'test: ["CMD", "redis-cli", "ping"]',
        "postgres:16-alpine",
        "POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}",
        "pg_isready",
        "grafana/grafana:11.2.0",
        "GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:?GRAFANA_ADMIN_PASSWORD is required}",
        "prom/prometheus:v2.53.0",
        "networks:",
        "internal:",
        "driver: bridge",
    ]

    assert_contains_all(text, required, "docker compose dependency hardening")


def test_docker_compose_has_no_duplicate_grafana_dashboard_mount():
    text = read(COMPOSE)
    mount = "./ops/grafana/dashboards:/var/lib/grafana/dashboards"
    assert text.count(mount) == 1, "Grafana dashboard mount must appear exactly once"


def test_dockerfile_keeps_public_and_private_targets_with_non_root_runtime():
    text = read(DOCKERFILE)

    required = [
        "FROM python:3.14-slim AS base",
        "FROM base AS private",
        "FROM base AS public",
        "ENV REQUIRE_PRIVATE_CGT_FOR_READINESS=true",
        "ENV REQUIRE_PRIVATE_CGT_FOR_READINESS=false",
        "cgtlib/_backend.py",
        "adduser --system --uid 1001",
        "USER app",
        "HEALTHCHECK --interval=30s",
        "CMD curl -f http://localhost:${PORT:-8000}/health/live || exit 1",
        'CMD ["sh", "-c", "uvicorn processual_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]',
    ]

    assert_contains_all(text, required, "Dockerfile production runtime")


def test_production_env_template_and_deployment_docs_stay_aligned_with_compose():
    env_text = read(ENV_TEMPLATE)
    docs_text = read(DEPLOYMENT_DOCS)

    required_env = [
        "ENVIRONMENT=production",
        "APP_ENV=production",
        "API_DEBUG=false",
        "JWT_SECRET=replace_with_long_random_jwt_secret_minimum_32_bytes",
        "API_KEYS=pmk_bootstrap_replace_with_strong_random_service_key",
        "PROCESSUAL_CRYPTO_KEY_B64=replace_with_base64_encoded_32_byte_encryption_key",
        "CORS_ORIGINS=https://your-frontend.example.com",
        "DATABASE_URL=postgresql+asyncpg://",
        "REDIS_URL=redis://:",
        "POSTGRES_PASSWORD=replace_with_strong_unique_postgres_secret",
        "REDIS_PASSWORD=replace_with_strong_unique_redis_secret",
        "GRAFANA_ADMIN_PASSWORD=replace_with_strong_unique_grafana_secret",
        "MAESTRO_ADMIN_EMAIL=admin@example.com",
        "MAESTRO_ADMIN_PASSWORD=replace_with_strong_unique_maestro_admin_password",
        "AUTH_TOKEN_PEPPER=",
        "AUTH_RATE_LIMIT_PEPPER=",
        "AUTH_DELIVERY_KEY_RING_JSON=",
        "AUTH_DELIVERY_CURRENT_KEY_VERSION=",
        "AUTH_PUBLIC_BASE_URL=https://accounts.example.com",
        "AUTH_MFA_KEY_RING_JSON=",
        "AUTH_MFA_CURRENT_KEY_VERSION=v1",
        "ADMIN_MARKETPLACE_PAYMENT_DESTINATION_KEY_RING_JSON=",
        "ADMIN_MARKETPLACE_PAYMENT_DESTINATION_CURRENT_KEY_VERSION=payment-v1",
    ]

    required_docs = [
        "`public`",
        "`private`",
        "docker compose build api",
        "docker compose up -d",
        "PROCESSUAL_CRYPTO_KEY_B64",
        "Docker secrets",
        "Kubernetes secrets",
        "Google Secret Manager",
        "Provider credentials are not bundled with Processual Maestro",
    ]

    forbidden_docs = [
        "--build-arg BUILD_TARGET=public",
        "`full`",
        "or `full` with CGT",
    ]

    assert_contains_all(env_text, required_env, "production env template")
    assert_contains_all(docs_text, required_docs, "deployment docs")
    present = [marker for marker in forbidden_docs if marker in docs_text]
    assert not present, f"Deployment docs still contain outdated Docker target markers: {present}"
