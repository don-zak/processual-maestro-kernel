from pathlib import Path

CONSOLE_CSS = Path("processual_api/static/css/console.css")


def test_primary_and_secondary_button_styles_are_defined() -> None:
    css = CONSOLE_CSS.read_text(encoding="utf-8")

    assert ".btn.primary{" in css
    assert "background:var(--amber)" in css
    assert "color:var(--void)" in css
    assert ".btn.secondary{" in css
    assert "background:var(--surface-2)" in css
    assert "color:var(--bright)" in css


def test_disabled_buttons_remain_visibly_distinct() -> None:
    css = CONSOLE_CSS.read_text(encoding="utf-8")

    assert ".btn:disabled{" in css
    assert "cursor:not-allowed" in css
    assert "opacity:0.55" in css
