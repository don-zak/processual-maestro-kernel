from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_settings_operations_center_is_bootstrapped() -> None:
    app = _text("processual_api/static/js/app.js")
    ui = _text("processual_api/static/js/settings_operations_18.js")
    css = _text("processual_api/static/css/settings_operations_18.css")

    assert "bootstrapSettingsOperations18" in app
    assert "settings_operations_18.js" in app
    assert "settings_operations_18.css" in app
    assert "PMK_SETTINGS_OPERATIONS_18" in app
    assert "settings-operations-root" in ui
    assert ".sops-hero" in css
    assert ".sops-grid" in css


def test_settings_operations_center_executes_safe_client_actions() -> None:
    ui = _text("processual_api/static/js/settings_operations_18.js")

    assert "Client operations center" in ui
    assert "Configure, validate, and operate safely" in ui
    assert "CLIENT.post('/settings/client/api-keys'" in ui
    assert "/settings/client/api-keys/${encodeURIComponent(keyId)}/rotate" in ui
    assert "CLIENT.del(`/settings/client/api-keys/${encodeURIComponent(keyId)}`)" in ui
    assert "Open provider setup" in ui
    assert "Open institution workspace" in ui
    assert "Copy this key now — it will not be shown again." in ui


def test_settings_operations_center_keeps_supervisor_scope_precise() -> None:
    ui = _text("processual_api/static/js/settings_operations_18.js").lower()

    assert "routine client-scoped actions run directly here" in ui
    assert "production approval required" in ui
    assert "write scopes" in ui
    assert "runtime connectors" in ui
    assert "raw key material is shown once" in ui

    forbidden = (
        "admin:*",
        "production_allowed=true",
        "runtime_connector_approved=true",
        "raw_secret_visible=true",
        "private_key=",
        "client_secret=",
    )
    for marker in forbidden:
        assert marker not in ui
