from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "reports" / (
    "MAESTRO_PLANS_SUPPORT_SUPERVISOR_LESSON_AR.md"
)


def test_supervisor_lesson_document_exists():
    assert DOC.exists()


def test_supervisor_lesson_documents_all_plan_names():
    text = DOC.read_text(encoding="utf-8")

    markers = (
        "Developer / Internal",
        "Starter / Pilot Starter",
        "Business",
        "Enterprise Integration Starter",
        "Enterprise Integration",
        "Enterprise Custom",
    )

    for marker in markers:
        assert marker in text


def test_supervisor_lesson_documents_allowances_and_business_prices():
    text = DOC.read_text(encoding="utf-8")

    for marker in (
        "2,000",
        "10,000",
        "100,000",
        "50,000",
        "500,000",
        "199 USD/month",
        "249 USD/month",
    ):
        assert marker in text


def test_supervisor_lesson_documents_margins_and_add_ons():
    text = DOC.read_text(encoding="utf-8")

    for marker in (
        "75% gross margin",
        "80% gross margin",
        "49.75 USD",
        "39.80 USD",
        "Extra 100k units",
        "Priority support",
        "Dedicated Slack/Teams",
        "SSO/RBAC",
        "Private/VPC deployment",
    ):
        assert marker in text


def test_supervisor_lesson_documents_byok_and_next_enforcement():
    text = DOC.read_text(encoding="utf-8")

    for marker in (
        "BYOK",
        "Provider tokens",
        "لا يبيع tokens",
        "pricing_decision(endpoint).units_charged",
        "consume_quota(amount=...)",
        "لا ندخل USD prices في backend enforcement",
    ):
        assert marker in text
