from pathlib import Path

APP_JS = Path("processual_api/static/js/app.js")
SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def test_app_initializes_settings_page_on_navigation() -> None:
    js = APP_JS.read_text(encoding="utf-8")

    assert "function navigateTo(pg)" in js
    # Settings Stage 18 uses modular bootstrap loaders.
    assert "function bootstrapSettingsOperations18()" in js
    assert "js/settings_operations_18.js?v=settingsops2" in js
    assert "function bootstrapSettingsLayout18()" in js
    assert "js/settings_layout_18.js?v=settingslayout1" in js
    assert "window.location.hash = 'page-' + pg;" in js
    assert "navigateTo(hash);" in js


def test_settings_init_is_idempotent_for_repeated_navigation() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "let settingsInitDone = false;" in js
    assert "if (settingsInitDone)" in js
    assert "settingsInitDone = true;" in js
    assert "initCollapsibleSettingsSections();" in js
    assert "refresh();" in js


def test_settings_lifecycle_keeps_collapsible_runtime_binding() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "collapseButton.onclick = () => collapseSettingsSections(true);" in js
    assert "expandButton.onclick = () => collapseSettingsSections(false);" in js
    assert "settingsSectionCards().forEach" in js
    assert "document.querySelector('#page-settings .settings-sections')" in js
