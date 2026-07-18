from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_cloudbuild_builds_versioned_and_latest_cloud_run_image() -> None:
    text = read_text("cloudbuild.yaml")

    assert "gcr.io/cloud-builders/docker" in text
    assert "build" in text
    assert "${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPOSITORY}/${_SERVICE}:${SHORT_SHA}" in text
    assert "${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPOSITORY}/${_SERVICE}:latest" in text
    assert "_REGION:" in text
    assert "_REPOSITORY:" in text
    assert "_SERVICE:" in text
    assert "gcloud run deploy" not in text
    assert "JWT_SECRET" not in text
    assert "MAESTRO_ADMIN_PASSWORD" not in text


def test_dockerfile_preserves_cloud_run_runtime_port_contract() -> None:
    text = read_text("Dockerfile")

    assert "${PORT:-8000}" in text
    assert "uvicorn processual_api.main:app" in text
    assert "--host 0.0.0.0" in text
    assert "--port ${PORT:-8000}" in text
    assert "http://localhost:${PORT:-8000}/health/live" in text


def test_readme_documents_explicit_cloud_run_deploy_contract() -> None:
    text = read_text("README.md")

    assert "Cloud Run deploy contract" in text
    assert "gcloud builds submit" in text
    assert "--config cloudbuild.yaml" in text
    assert "gcloud run deploy processual-maestro-api" in text
    assert "--set-secrets" in text
    assert "/health/live" in text
    assert "/health/ready" in text
    assert "BYOK" in text
    assert "provider costs are not included" in text


def test_readme_documents_required_production_environment_matrix() -> None:
    text = read_text("README.md")

    required_markers = [
        "Required production environment matrix",
        "ENVIRONMENT",
        "JWT_SECRET",
        "DATABASE_URL",
        "REDIS_URL",
        "MAESTRO_ADMIN_EMAIL",
        "MAESTRO_ADMIN_PASSWORD",
        "POSTGRES_PASSWORD",
        "REDIS_PASSWORD",
        "GRAFANA_ADMIN_PASSWORD",
        "Secret Manager",
        "CHANGE_ME_IN_PRODUCTION",
    ]

    for marker in required_markers:
        assert marker in text
