from pathlib import Path

from processual_api.settings import PRODUCTION_SECRET_ENV_VARS

ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_settings_exposes_canonical_production_secret_contract() -> None:
    expected = {
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
        "AUTH_DELIVERY_PROVIDER_TOKEN",
    }

    assert set(PRODUCTION_SECRET_ENV_VARS) == expected
    assert len(PRODUCTION_SECRET_ENV_VARS) == len(set(PRODUCTION_SECRET_ENV_VARS))


def test_cloud_run_readme_maps_every_secret_through_secret_manager() -> None:
    text = read_text("README.md")

    assert "Production secrets contract" in text
    assert "Secret Manager" in text
    assert "PRODUCTION_SECRET_ENV_VARS" in text

    for name in PRODUCTION_SECRET_ENV_VARS:
        assert f"{name}={name}:latest" in text


def test_cloudbuild_does_not_inline_secret_names_or_values() -> None:
    text = read_text("cloudbuild.yaml")

    for name in PRODUCTION_SECRET_ENV_VARS:
        assert name not in text

    forbidden_tokens = [
        "CHANGE_ME_IN_PRODUCTION",
        "replace_with_long_random_jwt_secret",
        "replace_with_base64_encoded_32_byte_encryption_key",
        "strong_unique",
        "sk-",
        "gsk_",
        "xoxb-",
    ]

    present = [token for token in forbidden_tokens if token in text]
    assert not present, f"cloudbuild.yaml contains secret-like tokens: {present}"


def test_production_env_template_covers_canonical_secret_contract() -> None:
    text = read_text(".env.production.example")

    for name in PRODUCTION_SECRET_ENV_VARS:
        assert f"{name}=" in text

