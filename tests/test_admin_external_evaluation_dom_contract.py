from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'processual_api' / 'static' / 'js' / 'admin_external_evaluation_dom_contract.js'


def _source() -> str:
    return SCRIPT.read_text(encoding='utf-8')


def test_external_evaluation_dom_contract_owns_category_and_surface_visibility() -> None:
    source = _source()

    required = [
        "const EXTERNAL_CATEGORY = 'external_evaluation'",
        "External Evaluation Access - governed sandbox evaluation",
        "const STANDARD_IDS = [",
        "admin-api-key-role",
        "admin-api-key-plan-id",
        "admin-api-key-client-id",
        "admin-api-key-scopes",
        "admin-api-key-generate-btn",
        "admin-api-key-profile-controls",
        "card.hidden = !external",
        "card.style.display = external ? '' : 'none'",
        "setStandardVisible(!external)",
    ]
    for marker in required:
        assert marker in source


def test_external_evaluation_dom_contract_self_heals_late_standard_injection() -> None:
    source = _source()

    assert 'new MutationObserver' in source
    assert "observer.observe(root, { childList: true, subtree: true })" in source
    assert "if (externalSelected()) window.setTimeout(apply, 0)" in source


def test_external_evaluation_dom_contract_blocks_standard_generate_clicks() -> None:
    source = _source()

    capture_start = source.index("document.addEventListener(\n    'click'")
    reconcile_start = source.index('function reconcile', capture_start)
    capture_source = source[capture_start:reconcile_start]

    assert "if (!externalSelected()) return" in capture_source
    assert "#admin-api-key-generate-btn" in capture_source
    assert 'event.preventDefault()' in capture_source
    assert 'event.stopImmediatePropagation()' in capture_source


def test_external_evaluation_dom_contract_exposes_governed_issue_flow_host() -> None:
    source = _source()

    required = [
        'External Evaluation Lifecycle',
        'Administrator Verification',
        'verify → provision → bind tasks → create grant → issue once → test → revoke',
        "const EVALUATION_HOST_ID = 'admin-evaluation-grants'",
        "window.PMK_ADMIN_SESSION?.check?.()",
        "mode.value = 'external_evaluation'",
        "mode.dispatchEvent(new Event('change', { bubbles: true }))",
    ]
    for marker in required:
        assert marker in source
