from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_settings_exposes_admin_audit_events_route() -> None:
    source = read_text("processual_api/routers/settings.py")

    assert "read_admin_audit_events" in source
    assert '@router.get("/admin/audit-events", response_model=dict)' in source
    assert "async def list_admin_audit_events" in source
    assert "_require_admin_audit_read(current_user)" in source
    assert "_admin_audit_path()" in source
    assert '"audit_events"' in source
    assert '"latest_count"' in source


def test_admin_loads_supervisor_audit_summary_script() -> None:
    source = read_text("processual_api/static/admin.html")

    assert "admin_supervisor_audit_summary.js" in source
    assert "adminsuperaudit01" in source
    assert 'id="admin-supervisor-audit-summary"' in source
    assert "Recent Supervisor Audit" in source


def test_supervisor_audit_summary_script_uses_safe_route_and_auth_bridge() -> None:
    source = read_text("processual_api/static/js/admin_supervisor_audit_summary.js")

    assert "Recent Supervisor Audit" in source
    assert "admin-supervisor-audit-summary" in source
    assert "/settings/admin/audit-events?limit=12" in source
    assert "window.PMK_ADMIN_AUTH" in source
    assert "auth.headers" in source
    assert "credentials: 'include'" in source
    assert "Accept: 'application/json'" in source


def test_supervisor_audit_summary_preserves_secret_boundary() -> None:
    source = read_text("processual_api/static/js/admin_supervisor_audit_summary.js")

    assert "visibility only" in source
    assert "Backend enforcement remains authoritative" in source
    assert "Do not display raw supervisor session keys" in source
    assert "raw_key" not in source
    assert "key_hash" not in source
    assert "provider_secret" not in source
    assert "encrypted_key" not in source
