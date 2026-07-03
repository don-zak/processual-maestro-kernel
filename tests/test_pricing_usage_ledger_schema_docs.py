from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "reports" / "MAESTRO_USAGE_LEDGER_SCHEMA.md"


def test_usage_ledger_schema_doc_exists():
    assert DOC.exists()


def test_usage_ledger_schema_documents_pricing_and_byok_fields():
    text = DOC.read_text(encoding="utf-8")

    for marker in (
        "pricing_version",
        "2026-07-byok-v1",
        "billing_policy",
        "byok",
        "billing_scope",
        "maestro_usage_units",
        "provider_cost_included",
        "BYOK",
    ):
        assert marker in text


def test_usage_ledger_schema_documents_quota_fields():
    text = DOC.read_text(encoding="utf-8")

    for marker in (
        "quota_scope",
        "quota_limit",
        "quota_used",
        "quota_requested",
        "quota_remaining",
        "quota_before",
        "quota_after",
        "quota_rejected",
        "plan_id",
    ):
        assert marker in text


def test_usage_ledger_schema_documents_success_and_rejection_guidance():
    text = DOC.read_text(encoding="utf-8")

    for marker in (
        "Successful Request Meaning",
        "Rejected Request Meaning",
        "status_code = 429",
        "quota_rejected = true",
        "Supervisor Checklist",
        "Minimal Required Ledger Fields",
    ):
        assert marker in text


def test_usage_ledger_schema_documents_customer_answers():
    text = DOC.read_text(encoding="utf-8")

    for marker in (
        "Why was my request rejected?",
        "Did you charge me for a rejected request?",
        "Does this include LLM provider cost?",
        "provider tokens are BYOK",
    ):
        assert marker in text
