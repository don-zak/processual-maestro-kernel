from pathlib import Path

INDEX_HTML = Path("processual_api/static/index.html")
SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def _settings_page_html() -> str:
    text = INDEX_HTML.read_text(encoding="utf-8")
    start = text.index("<!-- ===== PAGE: Settings ===== -->")
    end = text.index("</div><!-- /content -->", start)
    return text[start:end]


def test_client_support_card_is_supervisor_message_center() -> None:
    html = _settings_page_html()

    assert 'id="set-client-support-card"' in html
    assert "Supervisor Messages &amp; Support" in html
    assert "Message the Maestro supervisor/admin team" in html
    assert "card settings-section" in html
    assert "settings-grid" in html
    assert "inp-group" in html
    assert "mono-block" in html


def test_client_support_card_exposes_supervisor_message_fields() -> None:
    html = _settings_page_html()

    markers = (
        "set-supervisor-message-type",
        "set-supervisor-message-plan",
        "set-supervisor-message-body",
        "set-supervisor-message-send",
        "set-supervisor-message-prefill",
        "set-supervisor-message-status",
        "Send supervisor message",
        "Prefill readiness review",
        "do not paste raw provider secrets",
    )
    for marker in markers:
        assert marker in html


def test_client_support_script_uses_existing_client_request_workflow() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "prepareClientSupportRequest" in js
    assert "sendSupervisorMessage" in js
    assert "prefillSupervisorReadinessReview" in js
    assert "focusSupervisorMessagesCard" in js
    assert "/settings/client-request" in js
    assert "loadClientRequests" in js

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
    support_slice = js[
        js.index("function focusClientRequestsCard"):
        js.index("function clientIntegrationGuideText")
    ]
    for marker in forbidden:
        assert marker not in support_slice


def test_client_support_preserves_readiness_and_guide_handoffs() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "prepareReadinessSupportRequest" in js
    assert "prepareIntegrationGuideSupportRequest" in js
    assert "Please review this client account readiness checklist" in js
    assert "copy-safe integration guide" in js
