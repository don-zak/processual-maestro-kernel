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


def test_settings_button_audit_waits_for_identity_before_index_fallback():
    source = read("qualification/vq1_button_action_validator_v2.py")
    assert "BUTTON_RESOLUTION_TIMEOUT_MS = 5000" in source
    resolver_pos = source.index("def _resolve_button_after_reload")
    stable_wait_pos = source.index(
        'stable.wait_for(state="visible", timeout=BUTTON_RESOLUTION_TIMEOUT_MS)',
        resolver_pos,
    )
    label_wait_pos = source.index(
        'by_label.first.wait_for(state="visible", timeout=BUTTON_RESOLUTION_TIMEOUT_MS)',
        resolver_pos,
    )
    index_pos = source.index('buttons.nth(index)', resolver_pos)
    assert stable_wait_pos < label_wait_pos < index_pos


def test_settings_button_audit_resets_both_tab_storage_authorities():
    source = read("qualification/vq1_button_action_validator_v2.py")
    reset_pos = source.index("def _reset_console_section_state(page, section: str) -> None:")
    navigate_pos = source.index("def navigate_console(page, section: str) -> str:")
    reset_block = source[reset_pos:navigate_pos]
    assert 'localStorage.setItem(key, value)' in reset_block
    assert 'sessionStorage.setItem(key, value)' in reset_block
    assert 'SETTINGS_DEFAULT_TAB = "operations"' in source


def test_long_card_collapse_controls_have_stable_reload_identity():
    source = read("processual_api/static/js/long_card_collapse.js")
    assert "function stableCardKey(card)" in source
    assert "function stableToggleId(card)" in source
    card_key_pos = source.index("card.dataset.pmkLongCardKey = stableCardKey(card);")
    button_id_pos = source.index("button.id = stableToggleId(card);")
    append_pos = source.index("tools.appendChild(button);")
    assert card_key_pos < button_id_pos < append_pos
    assert "return ordinal ? `${base}-${ordinal + 1}` : base;" in source
    assert "button.setAttribute('aria-label', 'Collapse long card');" in source

    validator = read("qualification/vq1_button_action_validator_v2.py")
    resolver_pos = validator.index("def _resolve_button_after_reload")
    id_pos = validator.index('page.locator(f"#{button_id}")', resolver_pos)
    label_pos = validator.index('get_by_role("button", name=label, exact=True)', resolver_pos)
    index_pos = validator.index('buttons.nth(index)', resolver_pos)
    assert id_pos < label_pos < index_pos
