from pathlib import Path

INDEX_HTML = Path("processual_api/static/index.html")
SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def _settings_page_html() -> str:
    text = INDEX_HTML.read_text(encoding="utf-8")
    start = text.index("<!-- ===== PAGE: Settings ===== -->")
    end = text.index("</div><!-- /content -->", start)
    return text[start:end]


def test_support_card_becomes_collapsible_supervisor_messages_area() -> None:
    html = _settings_page_html()

    assert 'id="set-client-support-card"' in html
    assert "Supervisor Messages" in html
    assert "Message the Maestro supervisor/admin team" in html
    assert "card settings-section" in html
    assert "settings-grid" in html
    assert "mono-block" in html


def test_supervisor_messages_card_has_safe_message_fields() -> None:
    html = _settings_page_html()

    markers = (
        "set-supervisor-message-type",
        "set-supervisor-message-plan",
        "set-supervisor-message-body",
        "set-supervisor-message-send",
        "set-supervisor-message-prefill",
        "set-supervisor-message-status",
        "do not paste raw provider secrets",
        "do not open payment checkout",
        "admin-only routes",
    )
    for marker in markers:
        assert marker in html


def test_supervisor_messages_script_uses_existing_client_request_endpoint() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    markers = (
        "sendSupervisorMessage",
        "prefillSupervisorReadinessReview",
        "focusSupervisorMessagesCard",
        "prepareClientSupportRequest",
        "/settings/client-request",
        "loadClientRequests",
        "Supervisor message sent",
    )
    for marker in markers:
        assert marker in js


def test_collapsible_settings_runtime_uses_robust_settings_root() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "function settingsPageRoot" in js
    assert "document.querySelector('#page-settings .settings-sections')" in js
    assert "document.querySelector('.settings-sections')" in js
    assert "document.getElementById('page-settings')" in js
    assert "function settingsSectionCards" in js
    assert "settingsSectionCards().forEach" in js
    assert "[data-page=\"settings\"] .settings-section" not in js
    assert "document.querySelector('[data-page=\"settings\"]')" not in js
    assert "collapseButton.onclick = () => collapseSettingsSections(true);" in js
    assert "\n    collapseSettingsSections(true);\n" not in js


def test_supervisor_messages_and_collapse_do_not_use_forbidden_routes() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    support_slice = js[
        js.index("function focusClientRequestsCard"):
        js.index("function clientIntegrationGuideText")
    ]
    collapse_slice = js[
        js.index("function settingsPageRoot"):
        js.index("async function loadClientSettings")
    ]

    forbidden_support = (
        "/applications",
        "/billing/checkout",
        "/billing/portal",
        "/settings/api-keys",
        "/settings/llm-provider",
        "/admin",
        "encrypted_key",
        "api_key",
    )
    for marker in forbidden_support:
        assert marker not in support_slice

    forbidden_collapse = (
        "CLIENT.get",
        "CLIENT.post",
        "CLIENT.put",
        "CLIENT.delete",
        "/admin",
        "/applications",
        "/billing/checkout",
        "/billing/portal",
    )
    for marker in forbidden_collapse:
        assert marker not in collapse_slice
