from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic" / "versions" / "20260805_0027_lemon_squeezy_reconciliation_decisions.py"


def test_reconciliation_decision_revision_extends_webhook_inbox_head() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260805_0027"' in source
    assert 'down_revision: str | None = "20260805_0026"' in source


def test_reconciliation_decision_ledger_is_immutable_and_cross_account_bound() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for marker in (
        "admin_market_lemon_squeezy_reconciliation_decisions",
        "uq_admin_market_ls_reconciliation_inbox",
        "uq_admin_market_ls_reconciliation_event_identity",
        "event_identity_hash",
        "customer_ref",
        "order_ref",
        "offer_ref",
        "action IN ('ignore', 'reconcile', 'requires_review')",
        "ondelete=\"RESTRICT\"",
    ):
        assert marker in source

    lowered = source.lower()
    assert "signature" not in lowered
    assert "signing_secret" not in lowered
    assert "raw_body" not in lowered


def test_reconciliation_decision_downgrade_is_guarded_and_offline_safe() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "context.is_offline_mode()" in source
    assert "op.get_bind()" in source
    assert "Downgrade blocked: Lemon Squeezy reconciliation decisions exist" in source
