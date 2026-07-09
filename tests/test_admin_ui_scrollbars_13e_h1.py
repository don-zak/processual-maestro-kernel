from pathlib import Path

ADMIN_UI_HARDENING_CSS = Path(
    "processual_api/static/css/admin_ui_hardening_13c.css"
).read_text(encoding="utf-8")


def test_admin_scrollbar_hardening_marker_present_13e_h1():
    assert "13E-H1 admin scrollbar hardening" in ADMIN_UI_HARDENING_CSS


def test_admin_scrollbars_are_widened_for_scrollable_surfaces_13e_h1():
    assert "scrollbar-width: auto" in ADMIN_UI_HARDENING_CSS
    assert "::-webkit-scrollbar" in ADMIN_UI_HARDENING_CSS
    assert "width: 14px" in ADMIN_UI_HARDENING_CSS
    assert "height: 14px" in ADMIN_UI_HARDENING_CSS


def test_admin_scrollbar_rule_targets_safe_admin_surfaces_13e_h1():
    for selector in [
        "#main",
        ".admin-page",
        ".card",
        ".mono-block",
        ".admin-table-wrap",
    ]:
        assert selector in ADMIN_UI_HARDENING_CSS
