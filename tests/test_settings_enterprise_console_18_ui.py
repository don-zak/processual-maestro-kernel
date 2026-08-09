from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "processual_api" / "static" / "js" / "app.js"
SCRIPT = (
    ROOT
    / "processual_api"
    / "static"
    / "js"
    / "settings_enterprise_console_18.js"
)
STYLE = (
    ROOT
    / "processual_api"
    / "static"
    / "css"
    / "settings_enterprise_console_18.css"
)


def test_enterprise_console_enhancement_is_bootstrapped() -> None:
    source = APP.read_text(encoding="utf-8")

    assert "bootstrapSettingsEnterpriseConsole18" in source
    assert "settings_enterprise_console_18.css" in source
    assert "settings_enterprise_console_18.js" in source
    assert "PMK_SETTINGS_ENTERPRISE_CONSOLE_18?.init?.()" in source


def test_enterprise_console_is_server_authoritative_and_read_only() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "'/settings/enterprise-integration'" in source
    assert "CLIENT.get(ENDPOINT)" in source
    assert "payload.canonical_plan_id" in source
    assert "payload.scope_posture" in source
    assert "posture.source === 'catalog'" in source
    assert "not a grant of client permissions" in source
    assert "Production access remains blocked" in source
    assert "Runtime connector approval requires supervised qualification" in source
    assert "production_allowed === false" in source
    assert "runtime_connector_approved === false" in source

    assert "document.createElement('button')" not in source
    assert ".innerHTML =" not in source
    assert ".textContent" in source


def test_enterprise_console_has_accessible_live_status_and_fail_closed_error() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "aria-live', 'polite'" in source
    assert "aria-busy" in source
    assert "role', 'region'" in source
    assert "role', 'status'" in source
    assert "No production access has been inferred or granted" in source
    assert "Maestro fails closed" in source
    assert "enhancedState === 'error'" in source
    assert "refresh(force = false)" in source


def test_enterprise_console_retry_invalidates_previous_success_signature() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    failure_start = source.index("function renderFailure()")
    refresh_start = source.index("async function refresh", failure_start)
    failure_source = source[failure_start:refresh_start]

    assert "lastRenderedSignature = '';" in failure_source
    assert "refresh(force = false)" in source
    assert "if (!force && (enhancedState === 'true' || enhancedState === 'error')) return;" in source


def test_enterprise_console_styles_are_responsive_and_rtl_safe() -> None:
    source = STYLE.read_text(encoding="utf-8")

    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in source
    assert "@media (max-width: 760px)" in source
    assert "@media (max-width: 520px)" in source
    assert "@media (prefers-reduced-motion: reduce)" in source
    assert "border-inline-start" in source
    assert "overflow-wrap: anywhere" in source
    assert "font-variant-numeric: tabular-nums" in source
