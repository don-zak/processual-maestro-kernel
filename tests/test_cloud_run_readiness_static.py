from __future__ import annotations

from pathlib import Path


def test_dockerfile_uses_cloud_run_port_and_healthcheck() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "${PORT:-8000}" in dockerfile
    assert "/health/live" in dockerfile
    assert "processual_api.main:app" in dockerfile
    assert '"--port", "8000"' not in dockerfile


def test_readme_documents_cloud_run_readiness() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "Cloud Run readiness" in readme
    assert "${PORT:-8000}" in readme
    assert "/health/live" in readme
    assert "/health/ready" in readme
    assert "JWT_SECRET" in readme
    assert "DATABASE_URL" in readme
    assert "REDIS_URL" in readme
    assert "BYOK" in readme
