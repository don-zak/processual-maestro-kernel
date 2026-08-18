from __future__ import annotations

from pathlib import Path

import pytest

from processual_api.release_gate import (
    EXPECTED_ALEMBIC_HEAD,
    evaluate_release_environment,
)


def _valid_environment() -> dict[str, str]:
    return {
        "ENVIRONMENT": "staging",
        "JWT_SECRET": "j" * 48,
        "API_KEYS": "service-key-" + "a" * 32,
        "PROCESSUAL_CRYPTO_KEY_B64": "c" * 44,
        "DATABASE_URL": "postgresql+asyncpg://app:strong-password@db:5432/app",
        "REDIS_URL": "rediss://:strong-password@redis:6379/0",
        "MAESTRO_ADMIN_EMAIL": "admin@maestro.invalid",
        "MAESTRO_ADMIN_PASSWORD": "m" * 40,
        "POSTGRES_PASSWORD": "p" * 40,
        "REDIS_PASSWORD": "r" * 40,
        "GRAFANA_ADMIN_PASSWORD": "g" * 40,
        "AUTH_TOKEN_PEPPER": "t" * 40,
        "AUTH_RATE_LIMIT_PEPPER": "l" * 40,
        "AUTH_DELIVERY_KEY_RING_JSON": '{"v1":"key-material"}',
        "AUTH_DELIVERY_CURRENT_KEY_VERSION": "v1",
        "AUTH_DELIVERY_PROVIDER_URL": "https://mail.maestro.invalid/send",
        "AUTH_DELIVERY_PROVIDER_TOKEN": "d" * 40,
        "AUTH_PUBLIC_BASE_URL": "https://accounts.maestro.invalid",
        "AUTH_MFA_KEY_RING_JSON": '{"v1":"mfa-material"}',
        "AUTH_MFA_CURRENT_KEY_VERSION": "v1",
        "ADMIN_MARKETPLACE_PAYMENT_DESTINATION_KEY_RING_JSON": (
            '{"v1":"payment-material"}'
        ),
        "ADMIN_MARKETPLACE_PAYMENT_DESTINATION_CURRENT_KEY_VERSION": "v1",
        "LEMONSQUEEZY_API_KEY": "lemon-api-key-" + "k" * 32,
        "LEMONSQUEEZY_STORE_ID": "12345",
        "LEMONSQUEEZY_WEBHOOK_SECRET": "w" * 48,
        "LEMONSQUEEZY_CHECKOUT_SUCCESS_URL": (
            "https://app.maestro.invalid/console"
        ),
        "LEMONSQUEEZY_CHECKOUT_CANCEL_URL": (
            "https://app.maestro.invalid/pricing"
        ),
        "CORS_ORIGINS": "https://app.maestro.invalid",
        "API_DEBUG": "false",
        "AUDIT_ENABLED": "true",
        "RATE_LIMIT_ENABLED": "true",
    }


def test_valid_staging_and_production_environment_passes() -> None:
    staging = evaluate_release_environment(_valid_environment())
    assert staging.environment == "staging"
    assert staging.expected_alembic_head == "20260809_0046"
    assert EXPECTED_ALEMBIC_HEAD == "20260809_0046"
    assert set(staging.checks) == {
        "required_values",
        "secret_strength",
        "cors",
        "public_urls",
        "datastores",
        "runtime_controls",
    }

    production = _valid_environment()
    production["ENVIRONMENT"] = "production"
    assert evaluate_release_environment(production).environment == "production"


@pytest.mark.parametrize(
    ("name", "value"),
    (
        ("ENVIRONMENT", "development"),
        ("JWT_SECRET", "short"),
        ("LEMONSQUEEZY_API_KEY", "replace_with_lemon_api_key"),
        ("LEMONSQUEEZY_WEBHOOK_SECRET", "short"),
        ("LEMONSQUEEZY_STORE_ID", "0"),
        ("CORS_ORIGINS", "*"),
        ("CORS_ORIGINS", "http://app.maestro.invalid"),
        ("DATABASE_URL", "sqlite:///app.db"),
        ("REDIS_URL", "http://redis.invalid"),
        ("API_DEBUG", "true"),
        ("AUDIT_ENABLED", "false"),
        ("RATE_LIMIT_ENABLED", "false"),
        ("AUTH_PUBLIC_BASE_URL", "http://accounts.maestro.invalid"),
        (
            "LEMONSQUEEZY_CHECKOUT_SUCCESS_URL",
            "https://your-frontend.example.com/console",
        ),
    ),
)
def test_unsafe_release_environment_fails_closed(name: str, value: str) -> None:
    environment = _valid_environment()
    environment[name] = value
    with pytest.raises(RuntimeError, match="release gate"):
        evaluate_release_environment(environment)


@pytest.mark.parametrize(
    "name",
    (
        "LEMONSQUEEZY_API_KEY",
        "LEMONSQUEEZY_WEBHOOK_SECRET",
    ),
)
def test_missing_lemon_secret_fails_without_echoing_secret(name: str) -> None:
    environment = _valid_environment()
    environment.pop(name)
    with pytest.raises(RuntimeError) as captured:
        evaluate_release_environment(environment)
    assert name in str(captured.value)
    assert "lemon-api-key-" not in str(captured.value)
    assert "w" * 20 not in str(captured.value)


def test_release_workflow_requires_gates_before_publish() -> None:
    workflow_path = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "release.yml"
    )
    workflow = workflow_path.read_text(encoding="utf-8")
    required = (
        "Commercial release environment gate",
        "python -m processual_api.release_gate",
        "LEMONSQUEEZY_API_KEY: ${{ secrets.LEMONSQUEEZY_API_KEY }}",
        "Verify migration head",
        "20260809_0046",
        "Commercial staging smoke gate",
        "python -m processual_api.staging_smoke",
        "Run commercial regression gate",
        "Run all tests",
        "Ruff check",
        "Bandit security scan",
        "Check package metadata",
        "needs: release-gate",
    )
    for marker in required:
        assert marker in workflow

    gate_position = workflow.index("release-gate:")
    publish_position = workflow.index("publish:")
    assert gate_position < publish_position
