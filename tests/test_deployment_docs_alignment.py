from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DEPLOYMENT = ROOT / "DEPLOYMENT_EXTERNAL.md"
ENV_TEMPLATE = ROOT / ".env.production.example"
SECURITY_REPORT = ROOT / "docs" / "reports" / "PRODUCTION_SECURITY_READINESS.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_contains_all(text: str, markers: list[str], label: str):
    missing = [marker for marker in markers if marker not in text]
    assert not missing, f"Missing {label} markers: {missing}"


def test_readme_mentions_hardened_production_environment_template():
    text = read(README)

    required = [
        ".env.production.example",
        "ENVIRONMENT=production",
        "APP_ENV=production",
        "API_DEBUG=false",
        "PROCESSUAL_CRYPTO_KEY_B64",
        "CORS_ORIGINS",
        "GRAFANA_ADMIN_PASSWORD",
        "LEMONSQUEEZY_API_KEY",
        "OPENROUTER_API_KEY",
        "GENERIC_OPENAI_API_URL",
    ]

    assert_contains_all(text, required, "README production environment")


def test_readme_preserves_customer_owned_provider_key_model():
    text = read(README)

    required = [
        "Provider keys are customer-owned",
        "does not ship real OpenAI",
        "OpenRouter",
        "OpenCode",
        "generic OpenAI-compatible credentials",
    ]

    assert_contains_all(text, required, "README provider ownership")


def test_deployment_external_documents_extended_production_env_keys():
    text = read(DEPLOYMENT)

    required = [
        "Extended production environment variables",
        "ENVIRONMENT",
        "APP_ENV",
        "API_DEBUG",
        "PROCESSUAL_CRYPTO_KEY_B64",
        "SENTRY_ENVIRONMENT",
        "DISCORD_ADMIN_WEBHOOK_URL",
        "LEMONSQUEEZY_WEBHOOK_SECRET",
        "OPENROUTER_API_KEY",
        "OPENCODE_API_URL",
        "GENERIC_OPENAI_API_URL",
    ]

    assert_contains_all(text, required, "deployment external extended env")


def test_deployment_external_preserves_secret_manager_guidance():
    text = read(DEPLOYMENT)

    required = [
        "Do not use documentation sample values in production",
        "Docker secrets",
        "Kubernetes secrets",
        "Google Secret Manager",
        "secret-management system",
    ]

    assert_contains_all(text, required, "deployment secret manager guidance")


def test_env_template_security_report_and_deployment_docs_share_core_terms():
    env_text = read(ENV_TEMPLATE)
    report_text = read(SECURITY_REPORT)
    deployment_text = read(DEPLOYMENT)

    core_terms = [
        "ENVIRONMENT=production",
        "APP_ENV=production",
        "PROCESSUAL_CRYPTO_KEY_B64",
        "LEMONSQUEEZY_WEBHOOK_SECRET",
        "OPENROUTER_API_KEY",
        "GENERIC_OPENAI_API_URL",
        "DISCORD_ADMIN_WEBHOOK_URL",
        "SENTRY_ENVIRONMENT",
    ]

    for term in core_terms:
        assert term in env_text, f"Missing from env template: {term}"
        assert term in report_text, f"Missing from production security report: {term}"
        assert term in deployment_text, f"Missing from deployment docs: {term}"