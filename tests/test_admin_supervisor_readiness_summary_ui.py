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
    assert "adminsuperreadiness06" in source


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
    assert "path: '/health/live'" in source
    assert "path: '/health/ready'" in source
    assert "/auth/me" in source
    assert "/settings/admin/client-requests" in source
    assert "/settings/admin/audit-events?limit=3" in source
    assert "/settings/api-keys" in source
    assert "window.PMK_ADMIN_AUTH" in source
    assert "request.withCredentials = true" in source
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


def test_admin_supervisor_readiness_summary_includes_governor_and_adapters():
    source = Path("processual_api/static/js/admin_supervisor_readiness_summary.js").read_text(
        encoding="utf-8"
    )

    assert "Governor" in source
    assert "/cgt/govern/status" in source
    assert "Adapters" in source
    assert "Adapter Status" in source
    assert "/adapters/status" in source
    assert "Adapter Readiness" in source
    assert "/adapters/readiness" in source


def test_admin_supervisor_readiness_summary_does_not_render_secret_fields():
    source = Path("processual_api/static/js/admin_supervisor_readiness_summary.js").read_text(
        encoding="utf-8"
    )

    assert "raw_key" not in source
    assert "key_hash" not in source
    assert "provider_secret" not in source
    assert "encrypted_key" not in source

def test_readiness_summary_passes_admin_auth_headers_to_checks() -> None:
    source = Path("processual_api/static/js/admin_supervisor_readiness_summary.js").read_text(
        encoding="utf-8"
    )

    assert "function readinessFetch" in source
    assert "window.PMK_ADMIN_AUTH.headers" in source
    assert "new XMLHttpRequest" in source
    assert "request.withCredentials = true" in source

def test_readiness_summary_does_not_use_bridged_fetch_for_readiness_checks() -> None:
    source = Path("processual_api/static/js/admin_supervisor_readiness_summary.js").read_text(
        encoding="utf-8"
    )

    assert "window.PMK_ADMIN_AUTH.headers" in source
    assert "new XMLHttpRequest" in source
    assert "PMK_ADMIN_AUTH.fetch" not in source
    assert "bridgedFetch" not in source

def test_readiness_summary_uses_xhr_to_avoid_global_fetch_bridge() -> None:
    source = Path("processual_api/static/js/admin_supervisor_readiness_summary.js").read_text(
        encoding="utf-8"
    )

    assert "new XMLHttpRequest" in source
    assert "request.setRequestHeader" in source
    assert "headers.forEach" in source
    assert "window.PMK_ADMIN_AUTH.headers" in source
    assert "return fetch(path, options)" not in source
    assert "PMK_ADMIN_AUTH.fetch" not in source
    assert "bridgedFetch" not in source

def test_readiness_summary_does_not_gate_readiness_auth_headers_on_check_auth() -> None:
    source = Path("processual_api/static/js/admin_supervisor_readiness_summary.js").read_text(
        encoding="utf-8"
    )

    assert "window.PMK_ADMIN_AUTH.headers" in source
    assert "check.auth &&" not in source
