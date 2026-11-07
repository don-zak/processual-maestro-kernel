from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "processual_api" / "static" / "admin.html"
JS = ROOT / "processual_api" / "static" / "js"
SESSION = JS / "admin_session.js"
DOM_CONTRACT = JS / "admin_external_evaluation_dom_contract.js"
SECURITY_HEADERS = ROOT / "processual_api" / "middleware" / "security_headers.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_standard_api_key_surfaces_are_directly_loaded() -> None:
    html = _read(ADMIN)

    assert '/console/js/admin_api_keys.js?v=adminapikeys13eh2' in html
    assert '/console/js/admin_api_key_summary.js?v=adminapikeysummary01' in html
    assert '/console/js/admin_session.js?v=adminruntime05' in html


def test_external_evaluation_dom_contract_is_middleware_injected() -> None:
    middleware = _read(SECURITY_HEADERS)
    contract = _read(DOM_CONTRACT)

    assert 'admin_external_evaluation_dom_contract.js' in middleware
    assert 'if path in {"/admin", "/admin/"}' in middleware
    assert "External Evaluation Access - governed sandbox evaluation" in contract
    assert "setStandardVisible(!external)" in contract
    assert "window.PMK_ADMIN_SESSION?.check?.()" in contract


def test_protected_evaluation_assets_are_dynamic_not_obsolete() -> None:
    session = _read(SESSION)

    for marker in (
        '/console/js/admin_evaluation_grants.js?v=admineval-authority-v2',
        '/console/js/admin_evaluation_owned_preset.js?v=admineval-owned-preset-v1',
        '/console/js/admin_api_key_provisioning_workspace.js?v=adminapikeyworkspace-authority-v2',
        '/console/js/admin_api_key_evaluation_lifecycle.js?v=adminapikevaluation-authority-v2',
        "function loadProtectedEvaluationControls()",
        "const AUTHORITY_ENDPOINT = '/settings/admin/evaluation-grants/authority'",
        "authority?.authorized !== true",
        "authority?.authority !== 'platform_admin'",
        "document.body.dataset.adminEvaluationGrants = 'authorized'",
    ):
        assert marker in session

    assert session.index("document.body.dataset.adminEvaluationGrants = 'authorized'") < session.index(
        "loadProtectedEvaluationControls();"
    )


def test_protected_assets_exist_as_separate_behavior_modules() -> None:
    expected = {
        "admin_evaluation_grants.js": "One-time Evaluation API key created.",
        "admin_evaluation_owned_preset.js": "crm-context-owned",
        "admin_api_key_provisioning_workspace.js": "Provisioning Workspace",
        "admin_api_key_evaluation_lifecycle.js": "Evaluation Access & Key Handoff",
    }

    for filename, behavior_marker in expected.items():
        path = JS / filename
        assert path.is_file(), filename
        assert behavior_marker in _read(path), filename


def test_legacy_cache_comment_is_classified_as_debt_not_load_authority() -> None:
    html = _read(ADMIN)
    session = _read(SESSION)

    assert "15A legacy static compatibility markers" in html
    assert "adminsuperkeysux02" in html
    assert "adminsuperkeysux02" not in session
    assert "adminapikeyworkspace-authority-v2" in session
    assert "adminapikevaluation-authority-v2" in session
