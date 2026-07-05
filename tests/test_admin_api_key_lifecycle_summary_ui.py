from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_admin_loads_api_key_lifecycle_summary_script() -> None:
    source = read_text("processual_api/static/admin.html")

    assert "admin_api_key_summary.js" in source
    assert "adminapikeysummary01" in source


def test_api_key_lifecycle_summary_script_defines_visibility_counters() -> None:
    source = read_text("processual_api/static/js/admin_api_key_summary.js")

    assert "API Key Lifecycle Summary" in source
    assert "admin-api-key-lifecycle-summary" in source
    assert "summarizeKeys" in source
    assert "standard API keys" in source
    assert "supervisor session keys" in source
    assert "active" in source
    assert "revoked" in source
    assert "expired" in source


def test_api_key_lifecycle_summary_uses_existing_admin_routes() -> None:
    source = read_text("processual_api/static/js/admin_api_key_summary.js")

    assert "/settings/api-keys" in source
    assert "/settings/admin/supervisor-session-keys" in source
    assert "window.PMK_ADMIN_AUTH" in source
    assert "auth.headers" in source
    assert "credentials: 'include'" in source
    assert "Accept: 'application/json'" in source


def test_api_key_lifecycle_summary_preserves_secret_boundary() -> None:
    source = read_text("processual_api/static/js/admin_api_key_summary.js")

    assert "visibility only" in source
    assert "Backend enforcement remains authoritative" in source
    assert "Do not display raw supervisor session keys" in source
    assert "raw_key" not in source
    assert "key_hash" not in source
    assert "provider_secret" not in source
    assert "encrypted_key" not in source
