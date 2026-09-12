from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "processual_api" / "static" / "js"
LIFECYCLE = JS / "admin_api_key_evaluation_lifecycle.js"
EVALUATION = JS / "admin_evaluation_grants.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_every_evaluation_grant_card_carries_stable_grant_identity() -> None:
    source = _source(EVALUATION)
    for marker in (
        'data-eval-grant-card="true"',
        'data-eval-grant-id="${escapeHtml(grantId)}"',
        "const grantId = text(grant.grant_id)",
        "pmk-evaluation-grants-rendered",
    ):
        assert marker in source


def test_revoked_grants_keep_key_history_and_execution_audit_panels() -> None:
    source = _source(LIFECYCLE)
    for marker in (
        "const EVALUATION_LIST_ID = 'admin-eval-list'",
        "function evaluationGrantCards(host)",
        "function grantIdFromCard(card)",
        "card.dataset.evalGrantCard = 'true'",
        "card.dataset.evalGrantId = grantId",
        "loadKeyLifecyclePanel(keyPanel, grantId)",
        "loadAuditPanel(auditPanel, grantId)",
    ):
        assert marker in source
    assert "host.querySelectorAll('[data-eval-issue]').forEach" not in source


def test_revoked_grant_audit_attachment_does_not_depend_on_issue_button() -> None:
    source = _source(LIFECYCLE)
    decoration_start = source.index("function decorateGrantKeyLifecycle()")
    decoration_end = source.index("function observeGrantKeyLifecycle()", decoration_start)
    decoration = source[decoration_start:decoration_end]
    assert "evaluationGrantCards(host).forEach" in decoration
    assert "[data-eval-issue]" not in decoration
    assert "AUDIT_PANEL_ATTRIBUTE" in decoration
    assert "KEY_PANEL_ATTRIBUTE" in decoration
