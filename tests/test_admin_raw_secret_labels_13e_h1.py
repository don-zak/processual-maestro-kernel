from pathlib import Path

ADMIN_CLIENT_REQUESTS_JS = Path(
    "processual_api/static/js/admin_client_requests.js"
).read_text(encoding="utf-8")
ADMIN_INTEGRATION_READINESS_JS = Path(
    "processual_api/static/js/admin_integration_readiness.js"
).read_text(encoding="utf-8")


def test_integration_claim_raw_secret_label_is_not_rendered_verbatim_13e_h1():
    assert "<dt>raw_secret_visible</dt>" not in ADMIN_CLIENT_REQUESTS_JS
    assert "<dt>secret_visibility</dt>" in ADMIN_CLIENT_REQUESTS_JS


def test_readiness_security_controls_sanitize_raw_secret_labels_13e_h1():
    for source in [ADMIN_CLIENT_REQUESTS_JS, ADMIN_INTEGRATION_READINESS_JS]:
        assert "displaySecurityList13eH1(check.missing_security_controls)" in source
        assert "displaySecurityItem13eH1" in source
        assert '.replaceAll("raw_secret_visible", "secret_visibility")' in source
        assert '.replaceAll("raw_secret", "secret_value")' in source
        assert '.replaceAll("raw_key", "one_time_key")' in source
        assert '.replaceAll("key_hash", "stored_hash")' in source


def test_internal_payload_keys_remain_available_13e_h1():
    assert "raw_secret_visible: false" in ADMIN_CLIENT_REQUESTS_JS
    assert "payload.raw_secret_visible" in ADMIN_CLIENT_REQUESTS_JS
    assert "safe.raw_secret_visible" in ADMIN_CLIENT_REQUESTS_JS
