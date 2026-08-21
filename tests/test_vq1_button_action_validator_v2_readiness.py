from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_settings_button_audit_resolves_identity_before_index_after_reload():
    source = read("qualification/vq1_button_action_validator_v2.py")
    assert "def _resolve_button_after_reload(page, scope: str, item: dict[str, object]):" in source
    resolver_pos = source.index("def _resolve_button_after_reload")
    id_pos = source.index('page.locator(f"#{button_id}")', resolver_pos)
    label_pos = source.index('get_by_role("button", name=label, exact=True)', resolver_pos)
    index_pos = source.index('buttons.nth(index)', resolver_pos)
    assert id_pos < label_pos < index_pos
    assert '_accessible_label(candidate) == label' in source
    assert '"button identity no longer visible after deterministic reload"' in source
    assert "base.exercise_section_buttons = exercise_section_buttons" in source
