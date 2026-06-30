from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_TEMPLATE = ROOT / ".env.production.example"


def parse_env_template() -> dict[str, str]:
    values: dict[str, str] = {}

    for raw_line in ENV_TEMPLATE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

    return values


def test_production_env_template_exists_and_sets_production_mode():
    values = parse_env_template()

    assert ENV_TEMPLATE.is_file()
    assert values["ENVIRONMENT"] == "production"
    assert values["APP_ENV"] == "production"
    assert values["API_DEBUG"] == "false"


def test_production_env_template_covers_required_settings_secrets():
    values = parse_env_template()

    required = [
        "JWT_SECRET",
        "API_KEYS",
        "PROCESSUAL_CRYPTO_KEY_B64",
        "CORS_ORIGINS",
        "DATABASE_URL",
        "POSTGRES_PASSWORD",
        "REDIS_URL",
        "REDIS_PASSWORD",
        "GRAFANA_ADMIN_PASSWORD",
    ]

    missing = [key for key in required if key not in values]
    empty = [key for key in required if key in values and not values[key]]

    assert not missing, f"Missing required production env keys: {missing}"
    assert not empty, f"Required production env keys have empty placeholders: {empty}"


def test_production_env_template_covers_runtime_pool_rate_limit_and_audit_keys():
    values = parse_env_template()

    required = [
        "API_HOST",
        "API_PORT",
        "API_LOG_LEVEL",
        "DATABASE_POOL_MIN",
        "DATABASE_POOL_MAX",
        "RATE_LIMIT_ENABLED",
        "RATE_LIMIT_DEFAULT",
        "RATE_LIMIT_AUTHENTICATED",
        "AUDIT_ENABLED",
    ]

    missing = [key for key in required if key not in values]
    assert not missing, f"Missing runtime/rate-limit/audit env keys: {missing}"


def test_production_env_template_covers_observability_and_webhook_keys():
    values = parse_env_template()

    required = [
        "SENTRY_DSN",
        "SENTRY_ENVIRONMENT",
        "SENTRY_TRACES_SAMPLE_RATE",
        "PROMETHEUS_MULTIPROC_DIR",
        "DISCORD_WEBHOOK_URL",
        "DISCORD_ADMIN_WEBHOOK_URL",
        "DISCORD_RATE_LIMIT_SECONDS",
        "GRAFANA_ADMIN_USER",
        "GRAFANA_ADMIN_PASSWORD",
    ]

    missing = [key for key in required if key not in values]
    assert not missing, f"Missing observability/webhook env keys: {missing}"


def test_production_env_template_covers_billing_keys():
    values = parse_env_template()

    required = [
        "LEMONSQUEEZY_API_KEY",
        "LEMONSQUEEZY_STORE_ID",
        "LEMONSQUEEZY_WEBHOOK_SECRET",
        "LEMONSQUEEZY_CHECKOUT_SUCCESS_URL",
        "LEMONSQUEEZY_CHECKOUT_CANCEL_URL",
        "LS_VARIANT_STARTER",
        "LS_VARIANT_STARTER_YEARLY",
        "LS_VARIANT_PROFESSIONAL",
        "LS_VARIANT_PROFESSIONAL_YEARLY",
        "LS_VARIANT_ENTERPRISE",
        "LS_VARIANT_ENTERPRISE_YEARLY",
    ]

    missing = [key for key in required if key not in values]
    assert not missing, f"Missing billing env keys: {missing}"


def test_production_env_template_covers_provider_keys_and_customer_owned_model():
    values = parse_env_template()

    required = [
        "LLM_DEFAULT_PROVIDER",
        "OPENAI_API_KEY",
        "OPENAI_DEFAULT_MODEL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_DEFAULT_MODEL",
        "GEMINI_API_KEY",
        "GEMINI_DEFAULT_MODEL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_DEFAULT_MODEL",
        "OPENROUTER_API_KEY",
        "OPENROUTER_API_URL",
        "OPENROUTER_DEFAULT_MODEL",
        "OPENCODE_API_URL",
        "OPENCODE_API_KEY",
        "OPENCODE_DEFAULT_MODEL",
        "GENERIC_OPENAI_API_KEY",
        "GENERIC_OPENAI_API_URL",
        "GENERIC_OPENAI_DEFAULT_MODEL",
    ]

    missing = [key for key in required if key not in values]
    assert not missing, f"Missing provider env keys: {missing}"

    text = ENV_TEMPLATE.read_text(encoding="utf-8").lower()
    assert "customer/deploying organization owns its provider keys" in text
    assert "does not ship real third-party provider credentials" in text


def test_production_env_template_covers_cgt_governor_and_quota_keys():
    values = parse_env_template()

    required = [
        "CGT_GOVERNOR_ENABLED",
        "CGT_GOVERNOR_AUTO_REPAIR",
        "CGT_GOVERNOR_MAX_REPAIR_ROUNDS",
        "PMK_DEFAULT_API_KEY_QUOTA_LIMIT",
        "PMK_ENTERPRISE_PRIVATE_EVALUATION_QUOTA",
    ]

    missing = [key for key in required if key not in values]
    assert not missing, f"Missing CGT governor/quota env keys: {missing}"


def test_production_env_template_uses_no_known_real_or_dev_secrets():
    text = ENV_TEMPLATE.read_text(encoding="utf-8")

    forbidden_tokens = [
        "CHANGE_ME_IN_PRODUCTION",
        "dev-public-test-key",
        "sk-",
        "gsk_",
        "xoxb-",
        "whsec_",
    ]

    present = [token for token in forbidden_tokens if token in text]
    assert not present, f"Production template contains forbidden secret-like tokens: {present}"


def test_production_env_template_keeps_cors_explicit_not_wildcard():
    values = parse_env_template()

    assert values["CORS_ORIGINS"]
    assert values["CORS_ORIGINS"] != "*"
    assert values["CORS_ORIGINS"].startswith("https://")