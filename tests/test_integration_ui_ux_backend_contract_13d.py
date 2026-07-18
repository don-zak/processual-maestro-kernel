import re
from pathlib import Path

ROOT = Path(".")


def read(path: str) -> str:
    p = ROOT / path
    assert p.exists(), f"Missing expected file: {path}"
    return p.read_text(encoding="utf-8")


def test_13d_no_patch_or_recovery_accumulation_artifacts():
    forbidden_dirs = [
        p for p in ROOT.iterdir()
        if p.name == ".pmk_patch_backups" or p.name.startswith(".pmk_recovery_report_")
    ]
    forbidden_files = [
        p for p in ROOT.iterdir()
        if p.is_file()
        and (
            p.name.startswith(".pmk_patch")
            or p.name.startswith(".pmk_force")
            or p.name.startswith(".pmk_")
        )
        and p.suffix == ".py"
    ]
    assert not forbidden_dirs, f"Move recovery/backup dirs out of repo before continuing: {forbidden_dirs}"
    assert not forbidden_files, f"Move temporary patch scripts out of repo before continuing: {forbidden_files}"


def test_13d_13b_html_version_matches_real_js_marker():
    html = read("processual_api/static/admin.html")
    js = read("processual_api/static/js/admin_integration_pilot_controls_13b.js")

    match = re.search(r'admin_integration_pilot_controls_13b\.js\?v=([^"]+)', html)
    assert match, "admin.html must include the 13B script with an explicit cache-buster."

    html_version = match.group(1)

    js_version_match = re.search(r'const\s+VERSION\s*=\s*"([^"]+)"', js)
    assert js_version_match, "13B JS must declare const VERSION."

    js_version = js_version_match.group(1)

    assert html_version in js or html_version == js_version, (
        "Version truth violated: admin.html claims "
        f"{html_version!r}, but 13B JS declares {js_version!r} and does not contain the claimed marker."
    )


def test_13d_13b_scope_contract_is_consistent():
    main_py = read("processual_api/main.py")
    js = read("processual_api/static/js/admin_integration_pilot_controls_13b.js")

    backend_reads_scope_headers = (
        "X-Admin-Supervisor-Scopes" in main_py
        or "X-Admin-Supervisor-Scope" in main_py
    )

    frontend_sends_scope_headers = "X-Admin-Supervisor-Scopes" in js

    backend_derives_scopes = (
        "verify_supervisor_session" in main_py
        or "supervisor_session_keys" in main_py
        or "list_supervisor_session" in main_py
    )

    assert not backend_reads_scope_headers or frontend_sends_scope_headers or backend_derives_scopes, (
        "Scope contract mismatch: backend reads supervisor scope headers, "
        "but 13B JS does not send X-Admin-Supervisor-Scopes and backend derivation from session store was not detected."
    )


def test_13d_api_key_surface_contract_markers_exist():
    admin_html = read("processual_api/static/admin.html")
    api_js = read("processual_api/static/js/admin_api_keys.js")

    combined = admin_html + "\n" + api_js

    assert "Admin API Key Lifecycle" in combined or "API Keys" in combined
    assert "Safe metadata" in combined or "raw_key" in combined or "raw_secret" in combined
    assert "Backend scopes remain authoritative" in combined or "scopes remain authoritative" in combined


def test_13d_settings_readiness_binding_markers_exist():
    settings_js = read("processual_api/static/js/pages/settings.js")

    assert "/settings/client/usage-summary" in settings_js
    assert "integration" in settings_js.lower()
    assert "plan" in settings_js.lower()
