from pathlib import Path

INDEX_HTML = Path("processual_api/static/index.html")
SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def _settings_page_html() -> str:
    text = INDEX_HTML.read_text(encoding="utf-8")
    start = text.index("<!-- ===== PAGE: Settings ===== -->")
    end = text.index("</div><!-- /content -->", start)
    return text[start:end]


def test_client_support_card_uses_existing_client_ui() -> None:
    html = _settings_page_html()

    assert 'id="set-client-support-card"' in html
    assert "Support" in html
    assert "Quick support paths for onboarding" in html
    assert "card settings-section" in html
    assert "settings-grid" in html
    assert "inp-group" in html
    assert "mono-block" in html


def test_client_support_card_exposes_quick_actions() -> None:
    html = _settings_page_html()

    markers = (
        "set-support-onboarding",
        "set-support-provider",
        "set-support-billing",
        "set-support-enterprise",
        "set-client-support-status",
        "Prepare onboarding request",
        "Prepare provider setup request",
        "Prepare billing review request",
        "Prepare enterprise request",
    )
    for marker in markers:
        assert marker in html


def test_client_support_script_prefills_existing_request_workflow() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "prepareClientSupportRequest" in js
    assert "initClientSupportActions" in js
    assert "focusClientRequestsCard" in js
    assert "await loadClientRequests();" in js
    assert "set-client-request-type" in js
    assert "set-client-request-plan" in js
    assert "set-client-request-message" in js

    forbidden = (
        "/applications",
        "/billing/checkout",
        "/billing/portal",
        "/settings/llm-provider",
        "/settings/api-keys",
        "/admin",
        "admin_",
        "encrypted_key",
        "api_key",
    )
    for marker in forbidden:
        assert marker not in js


def test_client_support_quick_actions_preserve_safe_messages() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "No provider secrets are included" in js
    assert "Prepared support request. Review and submit." in js
    assert "Enterprise Integration upgrade" in js
