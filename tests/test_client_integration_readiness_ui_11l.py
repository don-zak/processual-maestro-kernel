from pathlib import Path

INDEX_HTML = Path("processual_api/static/index.html")
SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_client_integration_readiness_card_is_rendered_in_settings_shell():
    html = _read(INDEX_HTML)

    required_markers = [
        "set-integration-readiness-card",
        "Client integration readiness",
        "INTEGRATION-READINESS-11L",
        "set-integration-readiness-status",
        "set-integration-readiness-sandbox",
        "set-integration-readiness-production",
        "set-integration-readiness-runtime",
        "set-integration-readiness-missing-inputs",
        "set-integration-readiness-missing-controls",
        "set-integration-readiness-next-action",
        "set-integration-readiness-safety",
    ]

    for marker in required_markers:
        assert marker in html


def test_client_integration_readiness_uses_existing_settings_script():
    html = _read(INDEX_HTML)
    js = _read(SETTINGS_JS)

    assert "clientreadiness11l" in html
    assert "CLIENT_INTEGRATION_READINESS_11L_MARKER" in js
    assert "PMK_CLIENT_INTEGRATION_READINESS" in js
    assert "renderClientIntegrationReadiness" in js
    assert "set-api-key-operational-profile-selector" in js


def test_client_integration_readiness_guardrails_are_static_false():
    html = _read(INDEX_HTML)
    js = _read(SETTINGS_JS)

    combined = html + "\n" + js

    assert "Production connector approved" in combined
    assert "Runtime connector approved" in combined
    assert "rawSecretVisible = \"false\"" in js
    assert "externalHttpEnabled = \"false\"" in js
    assert "productionConnectorApproved = false" in js
    assert "runtimeConnectorApproved = false" in js
    assert "no raw secrets" in combined
    assert "no customer credentials" in combined
    assert "no external HTTP calls" in combined
    assert "no runtime connector" in combined


def test_client_integration_readiness_does_not_add_runtime_connector_or_external_http():
    js = _read(SETTINGS_JS)
    start = js.index("CLIENT_INTEGRATION_READINESS_11L_MARKER")
    block = js[start:]

    forbidden = [
        "requests.get",
        "requests.post",
        "httpx",
        "urllib",
        "fetch(",
        "XMLHttpRequest",
        "runtime_connector_approved = true",
        "runtimeConnectorApproved = true",
        "production_connector_approved = true",
        "productionConnectorApproved = true",
        "raw_secret_visible = true",
        "rawSecretVisible = true",
        "external_http_enabled = true",
        "externalHttpEnabled = true",
    ]

    for marker in forbidden:
        assert marker not in block
