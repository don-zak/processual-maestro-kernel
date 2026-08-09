from pathlib import Path


LAYOUT_JS = Path("processual_api/static/js/settings_layout_18.js")


def read_layout() -> str:
    return LAYOUT_JS.read_text(encoding="utf-8")


def test_enterprise_eligibility_card_is_grouped_with_integration_surface() -> None:
    js = read_layout()

    assert "set-enterprise-integration-eligibility-card" in js
    assert "return 'integration';" in js


def test_settings_tabs_have_bidirectional_aria_relationships() -> None:
    js = read_layout()

    assert "function tabId(key)" in js
    assert "function panelId(key)" in js
    assert 'aria-controls="${panelId(tab.key)}"' in js
    assert "panel.setAttribute('aria-labelledby', tabId(tab.key));" in js
    assert "panel.id = panelId(tab.key);" in js


def test_settings_tabs_support_standard_keyboard_navigation() -> None:
    js = read_layout()

    for marker in (
        "ArrowRight",
        "ArrowLeft",
        "Home",
        "End",
        "Enter",
        "event.key === ' '",
        "moveTabFocus",
        "handleTabKeydown",
    ):
        assert marker in js


def test_settings_tabs_keep_roving_tabindex_contract() -> None:
    js = read_layout()

    assert "button.tabIndex = active ? 0 : -1;" in js
    assert "aria-selected" in js
    assert "activate(event.currentTarget.dataset.sl18Tab, true);" in js
