from pathlib import Path

from fastapi.testclient import TestClient

from processual_api.main import app

ROOT = Path(__file__).resolve().parents[1]


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_external_api_key_runtime_keeps_governed_metadata_markers():
    security_source = _source(ROOT / "processual_api" / "auth" / "security.py")
    required_markers = [
        "api_key",
        "quota_limit",
        "usage_count",
        "last_used_at",
    ]
    for marker in required_markers:
        assert marker in security_source


def test_static_external_usage_routes_include_real_runtime_targets():
    app_source = "\n".join(
        [
            _source(ROOT / "processual_api" / "routers" / "cgt_governor.py"),
            _source(ROOT / "processual_api" / "routers" / "settings.py"),
        ]
    )

    required_markers = [
        "/adapters/status",
        "/cgt/govern",
        "X-API-Key",
        "quota_limit",
        "usage_count",
        "last_used_at",
    ]

    for marker in required_markers:
        assert marker in app_source


def test_external_api_key_usage_is_governed_and_evaluation_is_separate():
    ui_source = _source(ROOT / "processual_api" / "static" / "js" / "admin_api_keys.js")
    evaluation_source = _source(
        ROOT / "processual_api" / "static" / "js" / "admin_api_key_evaluation_lifecycle.js"
    )

    for marker in (
        "governed programmatic access",
        "not an authentication bypass",
        "revoke access when its operational purpose ends",
        "External Evaluation is governed separately",
        "fixed admitted-execution quota",
        "production disabled",
    ):
        assert marker in ui_source

    for marker in (
        "External Evaluation is subscription-free",
        "grant-first CRM/Integration authority",
        "one-time key handoff",
        "customer dashboard",
        "audit evidence",
    ):
        assert marker in evaluation_source


def test_external_usage_runtime_attempt_without_bearer_token_is_explicit():
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get(
        "/adapters/status",
        headers={
            "X-API-Key": "pmk_invalid_external_usage_probe",
        },
    )

    assert response.status_code in {401, 403, 429}
    assert "Bearer" not in response.request.headers
    assert response.request.headers["X-API-Key"] == "pmk_invalid_external_usage_probe"
