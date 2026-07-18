from pathlib import Path

INDEX_HTML = Path("processual_api/static/index.html")
SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def test_client_workspace_launch_path_markup_is_present() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "Client Workspace Launch Path" in html
    assert "set-client-launch-card" in html
    assert "set-launch-current-step" in html
    assert "set-launch-owner" in html
    assert "set-launch-primary-action" in html
    assert "set-launch-secondary-action" in html
    assert "set-launch-checklist" in html
    assert "Do not paste provider secrets or raw integration keys" in html


def test_client_workspace_launch_path_runtime_is_bound_to_readiness() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "function buildClientLaunchSteps" in js
    assert "function renderClientLaunchPath" in js
    assert "renderClientLaunchPath(integration, provider, requests);" in js
    assert "function initClientLaunchActions" in js
    assert "initClientLaunchActions();" in js
    assert "prepareProviderSetupRequest();" in js
    assert "prepareUsageReviewRequest();" in js
    assert "prepareIntegrationKeyRequest(\"provisioning\");" in js
    assert "focusClientRequestsCard();" in js


def test_client_workspace_launch_path_stays_client_safe() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    js = SETTINGS_JS.read_text(encoding="utf-8")
    launch_html = html[html.index("set-client-launch-card") : html.index("set-launch-checklist")]

    forbidden = (
        "/settings/api-keys",
        "/settings/llm-provider",
        "/admin",
        "encrypted_key",
        "api_key",
    )
    for marker in forbidden:
        assert marker not in launch_html
    assert "/settings/client-request" in js
    assert "/settings/client-requests" in js
