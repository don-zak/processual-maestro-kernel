from __future__ import annotations

from pathlib import Path

INDEX_HTML = Path("processual_api/static/index.html")
SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def _settings_page_html() -> str:
    text = INDEX_HTML.read_text(encoding="utf-8")
    start = text.index("<!-- ===== PAGE: Settings ===== -->")
    end = text.index("</div><!-- /content -->", start)
    return text[start:end]


def test_client_requests_billing_card_uses_existing_client_ui() -> None:
    html = _settings_page_html()

    assert 'id="set-client-requests-card"' in html
    assert "Requests &amp; Billing" in html
    assert "Client requests for billing, upgrades, integration, and support" in html
    assert "card settings-section" in html
    assert "settings-grid" in html
    assert "inp-group" in html
    assert "mono-block" in html


def test_client_requests_billing_card_has_safe_request_fields() -> None:
    html = _settings_page_html()

    markers = (
        "set-client-request-type",
        "set-client-request-plan",
        "set-client-request-message",
        "set-client-request-submit",
        "set-client-request-status",
        "set-client-request-history",
        "Latest request status history",
        "short id, type, requested plan, status, created_at, and source",
        "Do not paste provider secrets or raw keys",
        "Payment checkout and provider secret changes are not performed",
    )
    for marker in markers:
        assert marker in html


def test_client_requests_billing_script_uses_client_safe_settings_endpoints() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "/settings/client-request" in js
    assert "/settings/client-requests" in js
    assert "loadClientRequests" in js
    assert "submitClientRequest" in js
    assert "renderClientRequests" in js
    assert "clientRequestTypeLabel" in js
    assert "short_id" in js
    assert "request_type_label" in js
    assert "requested_plan" in js
    assert "created_at" in js
    assert "source" in js
    assert "Submitted requests will appear here newest first" in js

    forbidden = (
        "/applications",
        "/billing/checkout",
        "/billing/portal",
        "/settings/api-keys",
        "/settings/llm-provider",
        "/admin",
        "admin_",
        "encrypted_key",
        "api_key",
    )
    for marker in forbidden:
        assert marker not in js
