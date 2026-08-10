from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYOUT_JS = ROOT / "processual_api" / "static" / "js" / "settings_layout_18.js"
LAYOUT_CSS = ROOT / "processual_api" / "static" / "css" / "settings_layout_18.css"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_enterprise_console_loads_server_authoritative_contract():
    source = _read(LAYOUT_JS)

    assert "CLIENT.get('/settings/enterprise-integration')" in source
    assert "loadEnterpriseConsole" in source
    assert "enterpriseConsoleLoaded" in source
    assert "if (safeKey === 'integration')" in source


def test_enterprise_console_does_not_guess_plan_names_client_side():
    source = _read(LAYOUT_JS)
    console_start = source.index("function ensureEnterpriseConsoleCard")
    console_source = source[console_start:]

    assert "startsWith('enterprise')" not in console_source
    assert 'planId === "enterprise"' not in console_source
    assert "enterprise_integration_starter" not in console_source
    assert "enterprise_private" not in console_source


def test_enterprise_console_renders_dynamic_server_data_with_text_content():
    source = _read(LAYOUT_JS)

    assert "plan.textContent" in source
    assert "nextAction.textContent" in source
    assert "label.textContent" in source
    assert "action.textContent" in source
    assert "stages.replaceChildren()" in source


def test_enterprise_console_failure_is_fail_closed():
    source = _read(LAYOUT_JS)

    assert "renderEnterpriseConsoleError" in source
    assert "No production access has been granted." in source
    assert "Production access is not granted from Settings." in source
    assert "Runtime connector approval remains supervised and fail-closed." in source


def test_enterprise_console_has_responsive_status_hierarchy():
    source = _read(LAYOUT_CSS)

    assert ".sl18-enterprise-console" in source
    assert ".sl18-enterprise-badge" in source
    assert ".sl18-enterprise-stages" in source
    assert '.sl18-enterprise-stage[data-status="ready"]' in source
    assert "grid-template-columns: repeat(4, minmax(0, 1fr));" in source
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in source
    assert "grid-template-columns: 1fr;" in source
