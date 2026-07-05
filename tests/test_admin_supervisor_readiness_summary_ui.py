from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_admin_loads_program_supervision_readiness_summary() -> None:
    source = read_text("processual_api/static/admin.html")

    assert 'id="admin-program-supervision-readiness"' in source
    assert "Program &amp; Supervision Readiness" in source
    assert "program runtime and supervision readiness" in source
    assert "admin_supervisor_readiness_summary.js" in source
    assert "adminsuperreadiness01" in source


def test_supervisor_home_console_links_readiness_summary() -> None:
    source = read_text("processual_api/static/admin.html")

    assert 'href="#admin-program-supervision-readiness"' in source
    assert "Program &amp; Supervision Readiness" in source


def test_readiness_summary_script_checks_program_and_supervision_surfaces() -> None:
    source = read_text("processual_api/static/js/admin_supervisor_readiness_summary.js")

    assert "Program & Supervision Readiness" in source
    assert "admin-program-supervision-readiness" in source
    assert "program readiness" in source
    assert "supervision readiness" in source
    assert "/health" in source
    assert "/ready" in source
    assert "/auth/me" in source
    assert "/settings/admin/client-requests" in source
    assert "/settings/admin/audit-events?limit=3" in source
    assert "/settings/api-keys" in source
    assert "window.PMK_ADMIN_AUTH" in source
    assert "credentials: 'include'" in source
    assert "visibility-only" in source
    assert "Backend enforcement remains authoritative" in source


def test_readiness_summary_can_rehydrate_after_admin_runtime_changes() -> None:
    source = read_text("processual_api/static/js/admin_supervisor_readiness_summary.js")

    assert "ensureReadinessHost" in source
    assert "MutationObserver" in source
    assert "scheduleReadinessRefresh" in source
    assert "window.addEventListener('load'" in source
    assert "pmk-supervisor-session-key-updated" in source


def test_readiness_summary_preserves_secret_boundaries() -> None:
    source = read_text("processual_api/static/js/admin_supervisor_readiness_summary.js")

    assert "raw_key" not in source
    assert "key_hash" not in source
    assert "provider_secret" not in source
    assert "encrypted_key" not in source
