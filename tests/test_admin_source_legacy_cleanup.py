from pathlib import Path

INDEX = Path("processual_api/static/index.html")
CLIENT_REQUESTS = Path("processual_api/static/js/admin_client_requests.js")


def test_client_console_source_has_no_demo_mode_literal() -> None:
    source = INDEX.read_text(encoding="utf-8")
    assert '<span id="demo-badge">Readiness pending</span>' in source
    assert '<span id="demo-badge">Demo Mode</span>' not in source


def test_admin_client_requests_no_longer_reads_legacy_bearer_storage() -> None:
    source = CLIENT_REQUESTS.read_text(encoding="utf-8")
    for marker in (
        "localStorage.getItem('access_token')",
        "localStorage.getItem('auth_token')",
        "localStorage.getItem('admin_token')",
        "sessionStorage.getItem('access_token')",
        "sessionStorage.getItem('auth_token')",
        "sessionStorage.getItem('admin_token')",
    ):
        assert marker not in source
    assert "function authHeaders(extra)" in source
    assert "window.PMK_ADMIN_AUTH" in source
    assert "return { ...(extra || {}) };" in source


def test_admin_client_requests_uses_only_canonical_supervisor_storage_key() -> None:
    source = CLIENT_REQUESTS.read_text(encoding="utf-8")
    assert "'pmk_supervisor_session_key'" in source
    assert "'admin_supervisor_session_key'" not in source
    assert "'supervisor_session_key'" not in source
    assert "'pmk_sup_session_key'" not in source
    assert 'window.localStorage?.getItem("pmk_admin_supervisor_session")' not in source
    assert 'window.sessionStorage?.getItem("pmk_admin_supervisor_session")' not in source
    assert 'window.sessionStorage?.getItem("pmk_supervisor_session_key")' in source
