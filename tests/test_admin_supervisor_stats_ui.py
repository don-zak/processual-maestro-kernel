from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_admin_loads_supervisor_stats_script() -> None:
    source = read_text("processual_api/static/admin.html")

    assert "admin_supervisor_stats.js" in source
    assert "adminsuperstats01" in source


def test_supervisor_stats_script_defines_overview_counters() -> None:
    source = read_text("processual_api/static/js/admin_supervisor_stats.js")

    assert "Supervisor Overview" in source
    assert "admin-supervisor-overview-counters" in source
    assert "summarizeRequests" in source
    assert "requests by status" in source
    for marker in (
        "pending",
        "reviewed",
        "approved",
        "rejected",
        "completed",
        "Draft saved",
        "Response sent",
    ):
        assert marker in source


def test_supervisor_stats_fetches_client_requests_with_admin_auth_bridge() -> None:
    source = read_text("processual_api/static/js/admin_supervisor_stats.js")

    assert "/settings/admin/client-requests" in source
    assert "window.PMK_ADMIN_AUTH" in source
    assert "auth.headers" in source
    assert "credentials: 'include'" in source
    assert "Accept: 'application/json'" in source
    assert "method: 'GET'" in source


def test_supervisor_stats_are_visibility_only_not_permissions() -> None:
    source = read_text("processual_api/static/js/admin_supervisor_stats.js")

    assert "visibility only" in source
    assert "Backend enforcement remains authoritative" in source
    assert "Actions remain owned by the Clients page" in source
    assert "key_hash" not in source
    assert "provider_secret" not in source
    assert "encrypted_key" not in source
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert f"method: '{method}'" not in source


def test_admin_supervisor_overview_has_static_placeholder() -> None:
    source = read_text("processual_api/static/admin.html")

    assert 'id="admin-supervisor-overview-counters"' in source
    assert "Supervisor Overview" in source
    assert "Loading supervisor overview" in source


def test_supervisor_stats_refreshes_without_recreating_duplicate_cards() -> None:
    source = read_text("processual_api/static/js/admin_supervisor_stats.js")

    assert "scheduleRefresh" in source
    assert "window.addEventListener('load', scheduleRefresh)" in source
    assert "pmk-client-request-updated" in source
    assert "pmk-supervisor-session-key-updated" in source
    assert "document.getElementById(HOST_ID)" in source
    assert "MutationObserver" not in source
    assert "Supervisor Operations Center" not in source
    assert "admin-supervisor-home-console" not in source
