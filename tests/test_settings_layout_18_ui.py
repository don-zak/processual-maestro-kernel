from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_settings_layout_is_bootstrapped() -> None:
    app = _text("processual_api/static/js/app.js")
    layout = _text("processual_api/static/js/settings_layout_18.js")
    css = _text("processual_api/static/css/settings_layout_18.css")

    assert "bootstrapSettingsLayout18" in app
    assert "settings_layout_18.js" in app
    assert "settings_layout_18.css" in app
    assert "PMK_SETTINGS_LAYOUT_18" in app
    assert "sl18-tabs" in layout
    assert ".sl18-tabs" in css
    assert ".sl18-panel" in css


def test_settings_layout_uses_five_compact_groups() -> None:
    layout = _text("processual_api/static/js/settings_layout_18.js")

    for label in (
        "Operations",
        "Account",
        "Plan & usage",
        "Integration",
        "Escalations",
    ):
        assert label in layout

    assert "set-provider-connection-card" in layout
    assert "set-api-key-integration-card" in layout
    assert "set-client-requests-card" in layout
    assert "set-client-support-card" in layout


def test_provider_is_direct_self_service_and_request_button_is_hidden() -> None:
    layout = _text("processual_api/static/js/settings_layout_18.js")
    settings = _text("processual_api/static/js/pages/settings.js")

    assert "Test connection" in layout
    assert "Save encrypted connection" in layout
    assert "Remove connection" in layout
    assert "set-provider-setup-request-prepare" in layout
    assert "sl18-hidden" in layout
    assert "Direct self-service is enabled for provider setup" in layout

    assert "CLIENT.post('/settings/provider-connection/test'" in settings
    assert "CLIENT.put('/settings/provider-connection/setup'" in settings
    assert "CLIENT.del('/settings/provider-connection/setup'" in settings


def test_support_is_secondary_and_precise() -> None:
    layout = _text("processual_api/static/js/settings_layout_18.js")
    css = _text("processual_api/static/css/settings_layout_18.css")

    assert "Billing, plan, security, or approval exceptions only" in layout
    assert "Use only when direct operations cannot resolve the issue" in layout
    assert 'data-sl18-panel="support"' in css
    assert "Escalations only" in css
