from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORTAL = ROOT / "processual_api" / "static" / "evaluation.html"
PORTAL_JS = ROOT / "processual_api" / "static" / "js" / "evaluation_client_portal.js"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_workspace_exposes_buyer_readable_governed_proof_journey() -> None:
    html = source(PORTAL)

    for marker in (
        "Governed proof journey",
        "1 · Authority issued",
        "2 · Execution admitted",
        "3 · Policy enforced",
        "4 · Evidence produced",
        "What this evaluation is designed to prove",
        "A durable replay consumes no additional quota.",
        "A conflicting idempotency request is rejected without consuming quota.",
        "Revocation ends authority while historical evidence remains reviewable.",
        "Production execution is never authorized by an External Evaluation grant.",
    ):
        assert marker in html


def test_workspace_keeps_technical_details_available_without_leading_with_them() -> None:
    html = source(PORTAL)

    assert "<summary>Technical evaluation identity</summary>" in html
    assert "<summary>Technical execution details</summary>" in html
    for marker in (
        'id="grant-id"',
        'id="key-id"',
        'id="expires-at"',
        'id="task-id"',
        'id="binding-id"',
        'id="idempotency-key"',
        'id="task-input"',
        'id="execute"',
        'id="result"',
    ):
        assert marker in html


def test_workspace_security_and_authority_contract_remains_unchanged() -> None:
    html = source(PORTAL)
    js = source(PORTAL_JS)

    assert '<meta name="referrer" content="no-referrer" />' in html
    assert "The raw API key stays in this page's memory only." in html
    assert "PostgreSQL-backed" in html
    assert "Production execution: disabled" in html
    assert "evaluation_client_portal.js?v=eval-client-authority-v6" in html
    assert "localStorage" not in js
    assert "sessionStorage" not in js
    assert "credentials: 'omit'" in js
    assert "X-API-Key" in js
    assert "/evaluation/runtime/status" in js
    assert "/evaluation/runtime/task-execute" in js


def test_workspace_does_not_claim_client_side_authority() -> None:
    html = source(PORTAL)

    assert "backend-authoritative" in html
    assert "derived from the sealed backend grant authority" in html
    assert "server still rejects any task or binding outside the grant envelope" in html
    assert "browser-authoritative" not in html


def test_workspace_guides_customer_through_next_action_states() -> None:
    html = source(PORTAL)
    js = source(PORTAL_JS)

    for marker in (
        'id="next-action"',
        'id="next-action-title"',
        'id="next-action-copy"',
        'id="next-action-state"',
        "Recommended next step",
        "Connect your Evaluation key",
    ):
        assert marker in html

    for marker in (
        "function renderNextAction()",
        "Choose a runnable proof scenario",
        "Execute the prepared sandbox scenario",
        "Review the completed proof",
        "Evaluation quota is exhausted",
        "Credential is not executable",
    ):
        assert marker in js


def test_workspace_scenario_cards_are_accessible_and_backend_bounded() -> None:
    html = source(PORTAL)
    js = source(PORTAL_JS)

    assert "Runnable cards can be selected directly." in html
    for marker in (
        "scenario-badge",
        ".scenario-card.selected",
        "card.setAttribute('role', 'button')",
        "event.key === 'Enter' || event.key === ' '",
        "selectScenario(scenario.scenario_id)",
        "scenario.runnable !== true",
        "sealed backend grant authority",
        "No client-side capability was added.",
    ):
        assert marker in (html + js)
