from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from processual_api.admin_marketplace.lemon_squeezy_inbox import (
    LemonSqueezyWebhookInboxEntry,
)
from processual_api.admin_marketplace.lemon_squeezy_reconciliation_gate import (
    LemonSqueezyReconciliationContext,
    classify_lemon_squeezy_reconciliation,
)

NOW = datetime(2026, 8, 6, 10, 30, tzinfo=UTC)


def _entry(**overrides: object) -> LemonSqueezyWebhookInboxEntry:
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "event_identity_hash": "a" * 64,
        "payload_digest": "b" * 64,
        "event_name": "subscription_updated",
        "resource_type": "subscriptions",
        "external_resource_id": "9001",
        "store_id": "7001",
        "customer_ref": "customer_001",
        "order_ref": "order_001",
        "offer_ref": "starter_monthly",
        "test_mode": False,
        "processing_status": "received",
        "attempt_count": 0,
        "received_at": NOW,
        "evidence_schema_version": 1,
        "provider_customer_id": "501",
        "provider_order_id": "801",
        "provider_subscription_id": "9001",
        "variant_id": "301",
        "currency": None,
        "total_amount": None,
        "provider_status": "active",
        "provider_effective_at": NOW,
    }
    values.update(overrides)
    return LemonSqueezyWebhookInboxEntry(**values)  # type: ignore[arg-type]


def _context(**overrides: object) -> LemonSqueezyReconciliationContext:
    values: dict[str, object] = {
        "expected_customer_ref": "customer_001",
        "expected_order_ref": "order_001",
        "expected_offer_ref": "starter_monthly",
        "order_sales_channel": "lemon_squeezy",
        "offer_sales_channel": "lemon_squeezy",
        "production_mode": True,
        "expected_provider_customer_id": "501",
        "expected_provider_order_id": "801",
        "expected_provider_subscription_id": "9001",
        "expected_variant_id": "301",
    }
    values.update(overrides)
    return LemonSqueezyReconciliationContext(**values)  # type: ignore[arg-type]


def test_verified_subscription_evidence_reconciles() -> None:
    decision = classify_lemon_squeezy_reconciliation(
        entry=_entry(),
        context=_context(),
    )

    assert decision.action == "reconcile"
    assert decision.reason_code == "verified_evidence_requires_reconciliation"


@pytest.mark.parametrize(
    ("entry_overrides", "context_overrides", "reason"),
    [
        ({"evidence_schema_version": None}, {}, "verified_evidence_missing"),
        ({"provider_customer_id": "999"}, {}, "provider_customer_mismatch"),
        ({"provider_order_id": "999"}, {}, "provider_order_mismatch"),
        (
            {"provider_subscription_id": "999"},
            {},
            "provider_subscription_mismatch",
        ),
        ({"variant_id": "999"}, {}, "variant_mismatch"),
        (
            {"external_resource_id": "999"},
            {},
            "resource_provider_subscription_mismatch",
        ),
    ],
)
def test_explicit_subscription_evidence_mismatches_require_review(
    entry_overrides: dict[str, object],
    context_overrides: dict[str, object],
    reason: str,
) -> None:
    decision = classify_lemon_squeezy_reconciliation(
        entry=_entry(**entry_overrides),
        context=_context(**context_overrides),
    )

    assert decision.action == "requires_review"
    assert decision.reason_code == reason


def test_order_money_comparison_is_decimal_safe() -> None:
    decision = classify_lemon_squeezy_reconciliation(
        entry=_entry(
            event_name="order_created",
            resource_type="orders",
            external_resource_id="801",
            provider_subscription_id=None,
            currency="USD",
            total_amount="1000.00",
        ),
        context=_context(
            expected_provider_subscription_id=None,
            expected_currency="usd",
            expected_total_amount="1000",
        ),
    )

    assert decision.action == "reconcile"


def test_invoice_requires_parent_subscription_and_money() -> None:
    decision = classify_lemon_squeezy_reconciliation(
        entry=_entry(
            event_name="subscription_payment_success",
            resource_type="subscription-invoices",
            external_resource_id="1101",
            provider_order_id=None,
            provider_subscription_id=None,
            variant_id=None,
            currency="USD",
            total_amount="1000",
        ),
        context=_context(
            expected_provider_order_id=None,
            expected_provider_subscription_id=None,
            expected_variant_id=None,
            expected_currency="USD",
            expected_total_amount="1000",
        ),
    )

    assert decision.action == "requires_review"
    assert decision.reason_code == "invoice_evidence_incomplete"


def test_older_provider_event_requires_review() -> None:
    decision = classify_lemon_squeezy_reconciliation(
        entry=_entry(provider_effective_at=NOW),
        context=_context(latest_provider_effective_at=NOW + timedelta(minutes=1)),
    )

    assert decision.action == "requires_review"
    assert decision.reason_code == "stale_provider_event"


def test_equal_provider_effective_timestamp_is_not_stale() -> None:
    decision = classify_lemon_squeezy_reconciliation(
        entry=_entry(provider_effective_at=NOW),
        context=_context(latest_provider_effective_at=NOW),
    )

    assert decision.action == "reconcile"


@pytest.mark.parametrize(
    ("entry_overrides", "context_overrides", "reason"),
    [
        ({"provider_effective_at": None}, {}, "provider_effective_at_invalid"),
        (
            {"provider_effective_at": datetime(2026, 8, 6, 10, 30)},
            {},
            "provider_effective_at_invalid",
        ),
        (
            {},
            {"latest_provider_effective_at": datetime(2026, 8, 6, 10, 30)},
            "latest_provider_effective_at_invalid",
        ),
    ],
)
def test_invalid_provider_timestamps_require_review(
    entry_overrides: dict[str, object],
    context_overrides: dict[str, object],
    reason: str,
) -> None:
    decision = classify_lemon_squeezy_reconciliation(
        entry=_entry(**entry_overrides),
        context=_context(**context_overrides),
    )

    assert decision.action == "requires_review"
    assert decision.reason_code == reason
