from __future__ import annotations

from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_admin_claim_key_ui_markers_exist():
    admin_html = read("processual_api/static/admin.html")
    admin_js = read("processual_api/static/js/admin_client_requests.js")

    assert "admin-integration-claim-keys-host" in admin_html
    assert "Integration Claim Keys" in admin_html
    assert "adminclaim13a" in admin_js
    assert "PMK_ADMIN_INTEGRATION_CLAIM_KEYS_13A" in admin_js
    assert "/settings/admin/integration-claim-keys" in admin_js
    assert "data-admin-integration-claim-issued-once" in admin_js
    assert "data-admin-integration-claim-runtime-enabled" in admin_js
    assert "data-admin-integration-claim-production-allowed" in admin_js
    assert "data-admin-integration-claim-external-http" in admin_js
    assert "data-admin-integration-claim-raw-secret" in admin_js


def test_client_claim_key_ui_markers_exist():
    settings_js = read("processual_api/static/js/pages/settings.js")

    assert "settingsclaim13a" in settings_js
    assert "PMK_CLIENT_INTEGRATION_CLAIM_KEYS_13A" in settings_js
    assert "/settings/client/integration-claim-keys/redeem" in settings_js
    assert "/settings/client/integration-onboarding/status" in settings_js
    assert "settings-integration-claim-keys-host" in settings_js
    assert "data-settings-integration-claim-key-input" in settings_js
    assert "data-settings-integration-onboarding-case-count" in settings_js
    assert "data-settings-integration-claim-runtime-enabled" in settings_js
    assert "data-settings-integration-claim-production-allowed" in settings_js
    assert "data-settings-integration-claim-external-http" in settings_js
    assert "data-settings-integration-claim-secret-visible" in settings_js


def test_13a_documentation_exists_and_preserves_guardrails():
    doc = read("docs/integrations/INTEGRATION_ONBOARDING_13A.md")

    assert "Supervisor-Issued Integration Claim Keys" in doc
    assert "POST /settings/admin/integration-claim-keys" in doc
    assert "POST /settings/client/integration-claim-keys/redeem" in doc
    assert '"runtime_enabled": false' in doc
    assert '"production_allowed": false' in doc
    assert '"external_http_enabled": false' in doc
    assert '"raw_secret_visible": false' in doc
