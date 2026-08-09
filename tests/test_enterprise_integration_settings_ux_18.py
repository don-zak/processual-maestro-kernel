from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "processual_api" / "static" / "css" / "settings_layout_18.css"
LAYOUT_JS = ROOT / "processual_api" / "static" / "js" / "settings_layout_18.js"


def test_enterprise_integration_cards_remain_in_integration_tab() -> None:
    js = LAYOUT_JS.read_text(encoding="utf-8")

    markers = (
        "set-api-key-integration-card",
        "set-client-integration-guide-card",
        "set-integration-readiness-card",
        "return 'integration';",
    )
    for marker in markers:
        assert marker in js


def test_enterprise_integration_cards_receive_consistent_visual_hierarchy() -> None:
    css = CSS.read_text(encoding="utf-8")

    markers = (
        'data-sl18-panel="integration"',
        "#set-enterprise-integration-eligibility-card",
        "#set-api-key-integration-card",
        "#set-integration-readiness-card",
        "#set-client-integration-guide-card",
        "linear-gradient",
    )
    for marker in markers:
        assert marker in css


def test_enterprise_integration_controls_have_keyboard_focus_treatment() -> None:
    css = CSS.read_text(encoding="utf-8")

    assert "button:focus-visible" in css
    assert "box-shadow: 0 0 0 3px" in css


def test_settings_layout_respects_reduced_motion_and_mobile_navigation() -> None:
    css = CSS.read_text(encoding="utf-8")

    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "transition: none" in css
    assert "@media (max-width: 900px)" in css
    assert "scroll-snap-type: x proximity" in css
    assert "scroll-snap-align: start" in css
