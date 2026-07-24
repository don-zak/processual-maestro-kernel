from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = ROOT / "docker-compose.yml"


def _compose_text() -> str:
    return COMPOSE_PATH.read_text(
        encoding="utf-8"
    )


def _worker_block() -> str:
    content = _compose_text()

    start_marker = "  auth-delivery-worker:\n"
    end_marker = "\n  redis:\n"

    assert content.count(start_marker) == 1
    assert content.count(end_marker) == 1

    return content.split(
        start_marker,
        1,
    )[1].split(
        end_marker,
        1,
    )[0]


def test_delivery_worker_is_deployed_as_separate_service():
    block = _worker_block()

    assert "container_name: processual-auth-delivery-worker" in block

    assert (
        "processual_api.auth.delivery_worker"
        in block
    )

    assert "- --continuous" in block

    assert (
        "- --poll-interval-seconds"
        in block
    )

    assert (
        "${AUTH_DELIVERY_POLL_INTERVAL_SECONDS:-1}"
        in block
    )

    assert "\n    ports:" not in block
    assert "\n    expose:" not in block


def test_delivery_worker_has_required_secret_authorities():
    block = _worker_block()

    required_authorities = (
        "DATABASE_URL",
        "JWT_SECRET",
        "API_KEYS",
        "MAESTRO_ADMIN_EMAIL",
        "MAESTRO_ADMIN_PASSWORD",
        "AUTH_TOKEN_PEPPER",
        "AUTH_RATE_LIMIT_PEPPER",
        "AUTH_DELIVERY_KEY_RING_JSON",
        "AUTH_DELIVERY_CURRENT_KEY_VERSION",
        "AUTH_DELIVERY_PROVIDER_URL",
        "AUTH_DELIVERY_PROVIDER_TOKEN",
        "AUTH_PUBLIC_BASE_URL",
    )

    for authority in required_authorities:
        assert (
            f"${{{authority}:?"
            in block
        ), authority


def test_delivery_worker_has_bounded_runtime_controls():
    block = _worker_block()

    defaults = {
        "AUTH_DELIVERY_BATCH_SIZE": "25",
        "AUTH_DELIVERY_LEASE_SECONDS": "300",
        "AUTH_DELIVERY_MAX_ATTEMPTS": "8",
        "AUTH_DELIVERY_RETRY_BASE_SECONDS": "30",
        "AUTH_DELIVERY_RETRY_MAX_SECONDS": "3600",
        "AUTH_DELIVERY_REQUEST_TIMEOUT_SECONDS": "10",
    }

    for name, value in defaults.items():
        assert (
            f"${{{name}:-{value}}}"
            in block
        )


def test_delivery_worker_is_hardened_and_internal_only():
    block = _worker_block()

    assert "restart: unless-stopped" in block
    assert "stop_grace_period: 20s" in block
    assert "read_only: true" in block
    assert "no-new-privileges:true" in block
    assert 'memory: 256M' in block
    assert 'cpus: "0.5"' in block
    assert "driver: json-file" in block
    assert 'max-size: "10m"' in block
    assert 'max-file: "3"' in block

    assert (
        "networks:\n      - internal"
        in block
    )


def test_delivery_worker_waits_for_healthy_database():
    block = _worker_block()

    assert (
        "depends_on:\n"
        "      db:\n"
        "        condition: service_healthy"
        in block
    )


def test_delivery_worker_uses_public_image_target():
    block = _worker_block()

    assert (
        "build:\n"
        "      context: .\n"
        "      target: public"
        in block
    )
