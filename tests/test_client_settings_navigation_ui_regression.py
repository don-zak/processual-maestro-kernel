from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "processual_api" / "static" / "index.html"
SETTINGS_JS = ROOT / "processual_api" / "static" / "js" / "pages" / "settings.js"


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_client_settings_section_navigation_markup_exists() -> None:
    html = read_file(INDEX_HTML)

    assert "settings-section-nav" in html
    assert "Client settings sections" in html

    expected_targets = {
        "readiness": "Readiness",
        "account": "Account",
        "plan-usage": "Plan &amp; Usage",
        "integration-guide": "Integration Guide",
        "provider": "Provider",
        "requests": "Requests",
        "supervisor": "Supervisor",
    }

    for target, label in expected_targets.items():
        assert 'data-settings-nav-target="' + target + '"' in html
        assert 'data-settings-section-key="' + target + '"' in html
        assert label in html


def test_client_settings_section_navigation_runtime_exists() -> None:
    js = read_file(SETTINGS_JS)

    assert "function initSettingsSectionNavigation()" in js
    assert "[data-settings-nav-target]" in js
    assert "data-settings-section-key" in js
    assert "scrollIntoView" in js
    assert "settings-section-nav__button--active" in js


def test_client_settings_navigation_is_initialized_with_settings_lifecycle() -> None:
    js = read_file(SETTINGS_JS)

    assert js.count("initSettingsSectionNavigation();") >= 2
    assert "settingsInitDone" in js
    assert "initCollapsibleSettingsSections();" in js
