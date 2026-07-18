import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from processual_api.main import app
from processual_api.routers import settings as settings_router

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_ROUTER = ROOT / "processual_api" / "routers" / "settings.py"
SECURITY_MODULE = ROOT / "processual_api" / "auth" / "security.py"
MIDDLEWARE_MODULE = ROOT / "processual_api" / "middleware" / "usage_logging.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _admin_user() -> dict:
    return {
        "sub": "owner-admin",
        "client_id": "owner-admin",
        "role": "security_admin",
        "session_type": "ui_admin",
        "scopes": ["*"],
    }


def _create_external_api_key(
    *,
    monkeypatch,
    tmp_path,
    category: str = "pilot_client",
    scopes: list[str] | None = None,
) -> dict:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    body = settings_router.ApiKeyCreateRequest(
        category=category,
        role="client",
        scopes=scopes
        or [
            "read:health",
            "read:adapters",
            "read:governor",
            "run:govern",
        ],
        label="Tunisia pilot external access",
        purpose="introductory access for practical onboarding path",
        issued_to="external-tunisia-pilot",
        quota_limit_override=25,
        expires_at="2026-12-31T00:00:00+00:00",
        client_id="external-pilot-client",
        user_id="external-pilot-user",
    )

    return asyncio.run(
        settings_router.create_api_key(
            body=body,
            current_user=_admin_user(),
        )
    )


def test_admin_created_api_key_response_supports_external_usage_contract(
    monkeypatch,
    tmp_path,
):
    created = _create_external_api_key(monkeypatch=monkeypatch, tmp_path=tmp_path)

    assert created["api_key"].startswith("pmk_")
    assert created["onboarding_usage"]["header"] == "X-API-Key"
    assert created["onboarding_usage"]["example_endpoint"] == "/adapters/status"
    assert created["category"] == "pilot_client"
    assert created["purpose"] == "introductory access for practical onboarding path"
    assert created["issued_to"] == "external-tunisia-pilot"
    assert created["quota_limit_override"] == 25
    assert created["quota_limit"] == 25

    raw = settings_router._load_raw("owner-admin")
    stored = raw["api_keys"][0]

    assert stored["prefix"]
    assert stored["hashed"]
    assert "api_key" not in stored
    assert stored["category"] == "pilot_client"
    assert stored["status"] == "enabled"


def test_admin_created_api_key_is_listed_as_safe_metadata_only(
    monkeypatch,
    tmp_path,
):
    created = _create_external_api_key(monkeypatch=monkeypatch, tmp_path=tmp_path)

    listed = asyncio.run(settings_router.list_api_keys(current_user=_admin_user()))

    assert len(listed) == 1
    key = listed[0]

    assert key["id"] == created["id"]
    assert key["key_id"] == created["id"]
    assert key["prefix"] == created["prefix"]
    assert key["category"] == "pilot_client"
    assert key["role"] == "client"
    assert key["purpose"] == "introductory access for practical onboarding path"
    assert key["issued_to"] == "external-tunisia-pilot"
    assert key["quota_limit_override"] == 25
    assert key["quota_limit"] == 25

    assert "api_key" not in key
    assert "hashed" not in key


def test_admin_created_api_key_can_be_revoked_by_key_id(
    monkeypatch,
    tmp_path,
):
    created = _create_external_api_key(monkeypatch=monkeypatch, tmp_path=tmp_path)

    revoked = asyncio.run(
        settings_router.delete_api_key(
            key_id=created["id"],
            current_user=_admin_user(),
        )
    )

    assert revoked["status"] == "revoked"
    assert revoked["id"] == created["id"]
    assert revoked["revoked_at"]

    listed = asyncio.run(settings_router.list_api_keys(current_user=_admin_user()))
    assert listed == []

    raw = settings_router._load_raw("owner-admin")
    stored = raw["api_keys"][0]

    assert stored["status"] == "revoked"
    assert stored["revoked_at"] == revoked["revoked_at"]


def test_static_security_supports_x_api_key_without_browser_login():
    security_source = _source(SECURITY_MODULE)

    required_markers = [
        "X-API-Key",
        "API key",
        "api_key",
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


def test_external_api_key_usage_is_not_positioned_as_primary_sales_model():
    ui_source = _source(ROOT / "processual_api" / "static" / "js" / "admin_api_keys.js")

    required_markers = [
        "introductory access",
        "pilot access",
        "practical onboarding path",
        "not the primary sales model",
        "governed programmatic access",
        "not an authentication bypass",
        "revocable access",
    ]

    for marker in required_markers:
        assert marker in ui_source


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
