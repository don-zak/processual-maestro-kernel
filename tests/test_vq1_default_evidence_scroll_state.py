from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_default_evidence_refresh_resets_real_ui_scroll_containers():
    source = read("qualification/vq1_settings_default_evidence_refresh.py")
    assert "def reset_ui_scroll(page: Page) -> None:" in source
    assert "window.scrollTo(0, 0)" in source
    assert "'#content'" in source
    assert "'#main'" in source
    assert "element.scrollTop = 0" in source
    assert "element.scrollLeft = 0" in source


def test_default_evidence_refresh_recaptures_stable_admin_home():
    source = read("qualification/vq1_settings_default_evidence_refresh.py")
    validator = read("qualification/vq1_browser_state_validator.py")
    marker = "#admin-integration-readiness-tracking-summary-card"
    assert 'row["route"] == "/admin" and row["section"] == "home"' in source
    assert "def open_admin_home(" in source
    assert 'page.locator("#admin-home-canonical-surface").wait_for(' in source
    assert marker in source
    assert marker in validator
    assert "page.wait_for_timeout(2400)" in source
    assert "#admin-program-supervision-readiness" not in source
    admin_pos = source.index("def open_admin_home(")
    reset_pos = source.index("reset_ui_scroll(page)", admin_pos)
    assert reset_pos > admin_pos


def test_default_evidence_refresh_isolates_console_mocks_from_admin_capture():
    source = read("qualification/vq1_settings_default_evidence_refresh.py")
    assert 'console_page = browser.new_page(locale="en")' in source
    assert 'admin_page = browser.new_page(locale="en")' in source
    assert "establish_qualification_session(console_page)" in source
    assert "establish_qualification_session(admin_page)" in source
    assert "install_clean_console_routes(console_page)" in source
    assert "install_clean_console_routes(admin_page)" not in source
    assert "capture_page = admin_page" in source
