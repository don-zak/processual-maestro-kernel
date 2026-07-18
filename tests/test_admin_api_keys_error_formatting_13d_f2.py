from pathlib import Path

ADMIN_API_KEYS_JS = Path("processual_api/static/js/admin_api_keys.js")


def test_admin_api_keys_formats_object_error_details_without_object_object():
    source = ADMIN_API_KEYS_JS.read_text(encoding="utf-8")

    assert "function formatAdminApiErrorValue(" in source
    assert "function formatAdminApiError(" in source
    assert "throw new Error(formatAdminApiError(data, response.status));" in source
    assert "throw new Error(data.detail || data.error || `HTTP ${response.status}`);" not in source


def test_admin_api_keys_error_formatter_preserves_supervisor_session_storage_contract():
    source = ADMIN_API_KEYS_JS.read_text(encoding="utf-8")

    assert "pmk_supervisor_session_key" in source
    assert "sessionStorage.setItem(SUPERVISOR_SESSION_KEY_STORAGE_KEY, raw)" in source
    assert "sessionStorage.removeItem(SUPERVISOR_SESSION_KEY_STORAGE_KEY)" in source
