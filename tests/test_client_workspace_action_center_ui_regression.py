from pathlib import Path

INDEX_HTML = Path("processual_api/static/index.html")
SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def _action_center_html() -> str:
    html = INDEX_HTML.read_text(encoding="utf-8")
    start = html.index("set-client-action-center-card")
    end = html.index("set-action-center-status")
    return html[start:end]


def test_client_workspace_action_center_markup_is_present() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "Client Workspace Action Center" in html
    assert "set-client-action-center-card" in html
    assert "set-action-center-next" in html
    assert "set-action-center-owner" in html
    assert "set-action-center-pending" in html
    assert "set-action-center-last-request" in html
    assert "set-action-center-provider" in html
    assert "set-action-center-integration" in html
    assert "set-action-center-provider-action" in html
    assert "set-action-center-usage-action" in html
    assert "set-action-center-integration-action" in html
    assert "set-action-center-requests-action" in html


def test_client_workspace_action_center_runtime_is_bound() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "function renderClientWorkspaceActionCenter" in js
    assert "clientWorkspacePendingFollowUpCount" in js
    assert "clientWorkspaceLatestRequestSummary" in js
    assert "renderClientWorkspaceActionCenter(integration, provider, requests, current);" in js
    assert "bindClientWorkspaceActionButton" in js
    assert "prepareActionCenterProviderSetup" in js
    assert "prepareActionCenterUsageReview" in js
    assert "prepareActionCenterIntegrationKey" in js
    assert "openActionCenterRequests" in js
    assert "integration_key_rotation: 'Integration key rotation'" in js
    assert "integration_key_deactivation: 'Integration key deactivation'" in js


def test_client_workspace_action_center_stays_client_safe() -> None:
    launch_html = _action_center_html()

    forbidden = (
        "/settings/api-keys",
        "/settings/llm-provider",
        "/admin",
        "encrypted_key",
        "api_key",
    )
    for marker in forbidden:
        assert marker not in launch_html

    assert "Do not paste provider secrets or raw integration keys" in launch_html
