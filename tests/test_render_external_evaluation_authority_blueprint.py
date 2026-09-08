from __future__ import annotations

from pathlib import Path

BLUEPRINT = Path("render.yaml")


def _text() -> str:
    return BLUEPRINT.read_text(encoding="utf-8")


def test_render_keeps_sandbox_and_external_evaluation_authority_separate() -> None:
    text = _text()

    assert "name: processual-maestro-evaluation-sandbox" in text
    assert "dockerContext: ./deployment/evaluation-owned-sandbox" in text
    assert "name: processual-maestro-external-evaluation-authority" in text
    assert text.count("healthCheckPath: /health/live") == 2


def test_render_authority_uses_shared_postgres_and_redis_resources() -> None:
    text = _text()

    assert "name: processual-external-evaluation-authority-db" in text
    assert "property: connectionString" in text
    assert "name: processual-external-evaluation-authority-redis" in text
    assert "type: keyvalue" in text
    assert "key: DATABASE_URL" in text
    assert "key: REDIS_URL" in text


def test_render_authority_migrates_then_bootstraps_before_http_start() -> None:
    text = _text()

    migration = text.index("alembic upgrade head")
    bootstrap = text.index("python -m processual_api.auth.platform_admin_bootstrap_env")
    uvicorn = text.index("exec uvicorn processual_api.main:app")

    assert migration < bootstrap < uvicorn
    assert "key: ENVIRONMENT\n        value: evaluation" in text
    assert "key: PYTHON_VERSION\n        value: 3.14.3" in text


def test_render_authority_keeps_structured_secrets_out_of_git() -> None:
    text = _text()

    required_manual_secrets = (
        "AUTH_MFA_KEY_RING_JSON",
        "PROCESSUAL_CRYPTO_KEY_B64",
        "MAESTRO_ADMIN_EMAIL",
        "MAESTRO_ADMIN_PASSWORD",
        "AUTH_PLATFORM_ADMIN_BOOTSTRAP_SECRET",
        "AUTH_PLATFORM_ADMIN_BOOTSTRAP_SECRET_SHA256",
    )
    for key in required_manual_secrets:
        marker = f"- key: {key}\n        sync: false"
        assert marker in text

    assert "key: JWT_SECRET\n        generateValue: true" in text
    assert "key: AUTH_TOKEN_PEPPER\n        generateValue: true" in text
    assert "key: AUTH_RATE_LIMIT_PEPPER\n        generateValue: true" in text
