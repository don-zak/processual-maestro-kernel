from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "processual_api" / "static" / "js"
SUMMARY = JS / "admin_api_key_summary.js"
SESSION = JS / "admin_session.js"
RUNTIME_FIXUPS = JS / "admin_runtime_fixups.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_category_flow_owns_external_evaluation_card_creation() -> None:
    source = _source(SUMMARY)

    required = [
        "function ensureEvaluationCard()",
        "card.id = EVALUATION_CARD_ID",
        "card.dataset.lifecycleEmbedded = 'true'",
        "card.dataset.categoryOwned = 'true'",
        "External Evaluation Lifecycle",
        "Administrator Verification",
        "data-evaluation-grant-placeholder",
        "Boolean(ensureEvaluationCard())",
    ]
    for marker in required:
        assert marker in source

    # The category state must not depend on admin_session.js having created the card first.
    apply_start = source.index("function applyCategoryState()")
    bind_start = source.index("function bindCategory()", apply_start)
    apply_source = source[apply_start:bind_start]
    assert "const card = ensureEvaluationCard();" in apply_source
    assert "if (!card || !body) return false;" in apply_source


def test_external_evaluation_forces_standard_surfaces_out_of_layout() -> None:
    source = _source(SUMMARY)

    required = [
        "function setStandardVisibility(visible)",
        "node.hidden = true",
        "node.style.display = 'none'",
        "node.style.display = node.dataset.externalEvaluationPreviousDisplay || ''",
        "setStandardVisibility(!external)",
        "card.style.display = external ? '' : 'none'",
        "body.style.display = external ? '' : 'none'",
    ]
    for marker in required:
        assert marker in source


def test_external_category_directly_drives_mode_and_admin_verification() -> None:
    source = _source(SUMMARY)

    apply_start = source.index("function applyCategoryState()")
    bind_start = source.index("function bindCategory()", apply_start)
    apply_source = source[apply_start:bind_start]

    assert "if (external)" in apply_source
    assert "setMode('external_evaluation')" in apply_source
    assert "window.PMK_ADMIN_SESSION?.syncEvaluationSelectionState?.();" in apply_source
    assert "window.PMK_ADMIN_SESSION?.check?.();" in apply_source
    assert ".click()" not in apply_source
    assert "setMode('standard')" in apply_source
    assert "dispatchCategoryChanged();" in apply_source


def test_external_evaluation_still_blocks_standard_generation_at_runtime() -> None:
    runtime = _source(RUNTIME_FIXUPS)

    generation_start = runtime.index("async function generateProfiledApiKey()")
    profile_start = runtime.index("const profileName", generation_start)
    guard = runtime[generation_start:profile_start]

    assert "if (externalEvaluationSelected())" in guard
    assert "Standard API key generation is blocked for External Evaluation." in guard
    assert "return;" in guard


def test_session_loader_remains_compatible_with_category_owned_card() -> None:
    session = _source(SESSION)

    assert "function externalEvaluationSelected()" in session
    assert "function syncEvaluationSelectionState()" in session
    assert "window.addEventListener('pmk-api-key-category-changed'" in session
    assert "loadApiKeyProvisioningWorkspace();" in session
    assert "loadEvaluationGrantControls();" in session
    assert "loadApiKeyEvaluationLifecycle();" in session
    assert "Activate External Evaluation" not in session
    assert "applyExternalEvaluationActivation" not in session
