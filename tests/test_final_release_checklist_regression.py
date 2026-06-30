from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REQUIRED_RELEASE_FILES = [
    "README.md",
    "DEPLOYMENT_EXTERNAL.md",
    "SECURITY.md",
    ".env.production.example",
    "Dockerfile",
    "docker-compose.yml",
    "docs/reports/PRODUCTION_SECURITY_READINESS.md",
    "docs/reports/API_KEYS_ADAPTERS_REGRESSION_REPORT.md",
]


REQUIRED_PRODUCTION_TESTS = [
    "tests/test_production_startup_hardening_regression.py",
    "tests/test_auth_fallback_production_boundary.py",
    "tests/test_secret_encryption_readiness_regression.py",
    "tests/test_fastapi_integration_smoke.py",
    "tests/test_docker_compose_production_regression.py",
    "tests/test_final_release_checklist_regression.py",
]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def assert_contains_all(text: str, markers: list[str], label: str) -> None:
    missing = [marker for marker in markers if marker not in text]
    assert not missing, f"Missing {label} markers: {missing}"


def test_final_release_required_files_exist_and_are_nonempty():
    missing = [
        path
        for path in REQUIRED_RELEASE_FILES
        if not (ROOT / path).is_file()
    ]
    assert not missing, f"Missing required release files: {missing}"

    empty = [
        path
        for path in REQUIRED_RELEASE_FILES
        if not read(path).strip()
    ]
    assert not empty, f"Required release files are empty: {empty}"


def test_final_release_required_production_regression_tests_exist():
    missing = [
        path
        for path in REQUIRED_PRODUCTION_TESTS
        if not (ROOT / path).is_file()
    ]
    assert not missing, f"Missing production regression tests: {missing}"


def test_final_release_readme_preserves_production_and_customer_key_guidance():
    text = read("README.md")

    required = [
        "Processual Maestro Kernel",
        "ENVIRONMENT=production",
        "APP_ENV=production",
        "API_DEBUG=false",
        "JWT_SECRET",
        "API_KEYS",
        "PROCESSUAL_CRYPTO_KEY_B64",
        "DATABASE_URL",
        "REDIS_URL",
        "GRAFANA_ADMIN_PASSWORD",
        "Provider keys are customer-owned",
        "Never commit `.env` files or real provider API keys to GitHub",
    ]

    assert_contains_all(text, required, "README production release guidance")


def test_final_release_deployment_docs_preserve_external_docker_and_secret_guidance():
    text = read("DEPLOYMENT_EXTERNAL.md")

    required = [
        "`public`",
        "`private`",
        "docker compose build api",
        "docker compose up -d",
        "JWT_SECRET",
        "CORS_ORIGINS",
        "DATABASE_URL",
        "REDIS_URL",
        "PROCESSUAL_CRYPTO_KEY_B64",
        "Docker secrets",
        "Kubernetes secrets",
        "Google Secret Manager",
        "Provider credentials are not bundled with Processual Maestro",
    ]

    forbidden = [
        "--build-arg BUILD_TARGET=public",
        "`full`",
        "or `full` with CGT",
    ]

    assert_contains_all(text, required, "deployment release guidance")
    present = [marker for marker in forbidden if marker in text]
    assert not present, f"Deployment docs contain outdated release markers: {present}"


def test_final_release_security_readiness_records_current_production_gate():
    text = read("docs/reports/PRODUCTION_SECURITY_READINESS.md")

    required = [
        "PROD-RELEASE-01",
        "Final Release Gate Checkpoint",
        "168 passed, 6 warnings",
        "compileall: PASS",
        "git diff --check: clean",
        "git status --short: clean",
        "PROD-SEC-02",
        "PROD-SEC-03",
        "PROD-SEC-04",
        "PROD-SMOKE-01",
        "PROD-DOCKER-01",
        "tests/test_final_release_checklist_regression.py",
    ]

    assert_contains_all(text, required, "production security final release gate")


def test_final_release_env_template_and_gitignore_block_real_secret_workflow():
    env_text = read(".env.production.example")
    gitignore_text = read(".gitignore")

    required_env = [
        "ENVIRONMENT=production",
        "APP_ENV=production",
        "API_DEBUG=false",
        "JWT_SECRET=replace_with_long_random_jwt_secret_minimum_32_bytes",
        "API_KEYS=pmk_bootstrap_replace_with_strong_random_service_key",
        "PROCESSUAL_CRYPTO_KEY_B64=replace_with_base64_encoded_32_byte_encryption_key",
        "CORS_ORIGINS=https://your-frontend.example.com",
        "POSTGRES_PASSWORD=replace_with_strong_unique_postgres_secret",
        "REDIS_PASSWORD=replace_with_strong_unique_redis_secret",
        "GRAFANA_ADMIN_PASSWORD=replace_with_strong_unique_grafana_secret",
    ]

    assert_contains_all(env_text, required_env, "production env template")
    assert ".env" in gitignore_text