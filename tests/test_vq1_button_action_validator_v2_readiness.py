from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_settings_button_audit_waits_for_dynamic_action_surface_after_reload():
    source = read("qualification/vq1_button_action_validator_v2.py")
    assert "SETTINGS_DYNAMIC_BUTTON_IDS" in source
    assert '"set-provider-secret-test"' in source
    assert '"set-provider-secret-save"' in source
    assert '"set-provider-secret-clear"' in source
    assert "def _wait_for_settings_action_surface(page, section: str) -> None:" in source
    assert 'page.get_by_role("button", name="Collapse", exact=True)' in source
    navigate_pos = source.index("def navigate_console(page, section: str) -> str:")
    target_wait_pos = source.index('target.wait_for(state="visible", timeout=5000)', navigate_pos)
    readiness_pos = source.index("_wait_for_settings_action_surface(page, section)", navigate_pos)
    return_pos = source.index('return f"#page-{section}:visible"', navigate_pos)
    assert target_wait_pos < readiness_pos < return_pos
