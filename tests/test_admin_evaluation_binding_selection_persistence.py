from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNED_PRESET_SCRIPT = ROOT / "processual_api" / "static" / "js" / "admin_evaluation_owned_preset.js"


def _source() -> str:
    return OWNED_PRESET_SCRIPT.read_text(encoding="utf-8")


def test_prepared_binding_selection_survives_catalog_rerender() -> None:
    source = _source()
    for marker in (
        "const selectedBindingIds = new Set()",
        "function captureBindingSelection(event)",
        "function restoreBindingSelection()",
        "function ensureBindingSelectionPersistence()",
        "new MutationObserver",
        "input.checked = true",
        "window.PMK_ADMIN_EVALUATION_GRANTS?.updateReadiness?.()",
        "pmk-api-key-access-selection-changed",
    ):
        assert marker in source


def test_binding_selection_persistence_remains_memory_only_and_fail_closed() -> None:
    source = _source()
    assert "localStorage" not in source
    assert "sessionStorage" not in source
    assert "selectedBindingIds.delete(bindingId)" in source
    assert "if (target.disabled) return" in source
    assert "if (input.disabled)" in source


def test_binding_persistence_does_not_create_grants_or_keys() -> None:
    source = _source()
    assert "/issue-key" not in source
    assert "Create Evaluation Grant" not in source
    assert "api_key" not in source
