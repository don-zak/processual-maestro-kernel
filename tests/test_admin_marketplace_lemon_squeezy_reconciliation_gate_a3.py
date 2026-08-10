from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from processual_api.admin_marketplace.lemon_squeezy_inbox import (
    LemonSqueezyWebhookInboxEntry,
)
from processual_api.admin_marketplace.lemon_squeezy_reconciliation_gate import (
    LemonSqueezyReconciliationContext,
    classify_lemon_squeezy_reconciliation,
)


NOW = datetime(2026, 8, 5, 19, 0, tzinfo=timezone.utc)


def _entry(**overrides: object) -> LemonSqueezyWebhookInboxEntry:
    values: dict[str, object] = {
        "id": __import__("uuid").uuid4(),
        "event_identity_hash": "a" * 64,
        "payload_digest": "b" * 64,
        "event_name": "subscription_updated",
        "resource_type": "subscriptions",
        "external_resource_id": "9001",
        "store_id": "42",
        "customer_ref": "customer-1",
        "order_ref": "order-1",
        "offer_ref": "offer-1",
        "test_mode": False,
        "processing_status": "received",
        "attempt_count": 0,
        "received_at": NOW,
        "evidence_schema_version": 1,
        "provider_customer_id": "5001",
        "provider_order_id": "6001",
        "provider_subscription_id": "9001",
        "variant_id": "8001",
        "provider_status": "active",
        "provider_effective_at": NOW,
    }
    values.update(overrides)
    return LemonSqueezyWebhookInboxEntry(**values)


def _context(**overrides: object) -> LemonSqueezyReconciliationContext:
    values: dict[str, object] = {
        "expected_customer_ref": "customer-1",
        "expected_order_ref": "order-1",
        "expected_offer_ref": "offer-1",
        "order_sales_channel": "lemon_squeezy",
        "offer_sales_channel": "lemon_squeezy",
        "production_mode": True,
        "expected_provider_customer_id": "5001",
    }
    values.update(overrides)
    return LemonSqueezyReconciliationContext(**values)


def _snapshot(entry: LemonSqueezyWebhookInboxEntry) -> dict[str, object]:
    return deepcopy({name: getattr(entry, name) for name in entry.__dataclass_fields__})


def test_trusted_live_event_is_sent_to_reconciliation_without_mutation() -> None:
    entry = _entry()
    before = _snapshot(entry)

    decision = classify_lemon_squeezy_reconciliation(
        entry=entry,
        context=_context(),
    )

    assert decision.action == "reconcile"
    assert decision.reason_code == "verified_evidence_requires_reconciliation"
    assert _snapshot(entry) == before


@pytest.mark.parametrize(
    ("entry_overrides", "context_overrides", "reason_code"),
    (
        ({"resource_type": "orders"}, {}, "resource_type_mismatch"),
        ({"customer_ref": "customer-2"}, {}, "customer_binding_mismatch"),
        ({"order_ref": "order-2"}, {}, "order_binding_mismatch"),
        ({"offer_ref": "offer-2"}, {}, "offer_binding_mismatch"),
        ({}, {"order_sales_channel": "maestro_direct"}, "order_channel_mismatch"),
        ({}, {"offer_sales_channel": "maestro_direct"}, "offer_channel_mismatch"),
        ({"provider_customer_id": "5002"}, {}, "provider_customer_mismatch"),
        ({"test_mode": False}, {"production_mode": False}, "live_event_in_test_environment"),
    ),
)
def test_binding_or_environment_mismatch_requires_review(
    entry_overrides: dict[str, object],
    context_overrides: dict[str, object],
    reason_code: str,
) -> None:
    decision = classify_lemon_squeezy_reconciliation(
        entry=_entry(**entry_overrides),
        context=_context(**context_overrides),
    )

    assert decision.action == "requires_review"
    assert decision.reason_code == reason_code


def test_test_event_in_production_is_ignored() -> None:
    decision = classify_lemon_squeezy_reconciliation(
        entry=_entry(test_mode=True),
        context=_context(production_mode=True),
    )

    assert decision.action == "ignore"
    assert decision.reason_code == "test_event_in_production"


@pytest.mark.parametrize("status", ("processed", "rejected"))
def test_terminal_events_are_ignored(status: str) -> None:
    decision = classify_lemon_squeezy_reconciliation(
        entry=_entry(processing_status=status),
        context=_context(),
    )

    assert decision.action == "ignore"
    assert decision.reason_code == "event_already_terminal"


def test_unknown_event_requires_review_fail_closed() -> None:
    decision = classify_lemon_squeezy_reconciliation(
        entry=_entry(event_name="license_key_created"),
        context=_context(),
    )

    assert decision.action == "requires_review"
    assert decision.reason_code == "unsupported_event"


@pytest.mark.parametrize(
    ("event_name", "resource_type", "entry_overrides"),
    (
        (
            "order_created",
            "orders",
            {
                "external_resource_id": "6001",
                "evidence_schema_version": 3,
                "provider_order_id": "6001",
                "provider_subscription_id": None,
                "currency": "USD",
                "total_amount": "1999",
            },
        ),
        (
            "order_refunded",
            "orders",
            {
                "external_resource_id": "6001",
                "evidence_schema_version": 3,
                "provider_order_id": "6001",
                "provider_subscription_id": None,
                "currency": "USD",
                "total_amount": "1999",
            },
        ),
        ("subscription_created", "subscriptions", {}),
        ("subscription_cancelled", "subscriptions", {}),
        (
            "subscription_payment_success",
            "subscription-invoices",
            {
                "external_resource_id": "9101",
                "provider_order_id": None,
                "provider_subscription_id": "9001",
                "variant_id": None,
                "currency": "USD",
                "total_amount": "2499",
            },
        ),
        (
            "subscription_payment_failed",
            "subscription-invoices",
            {
                "external_resource_id": "9101",
                "provider_order_id": None,
                "provider_subscription_id": "9001",
                "variant_id": None,
                "currency": "USD",
                "total_amount": "2499",
            },
        ),
    ),
)
def test_supported_event_resource_pairs_reconcile(
    event_name: str,
    resource_type: str,
    entry_overrides: dict[str, object],
) -> None:
    decision = classify_lemon_squeezy_reconciliation(
        entry=_entry(
            event_name=event_name,
            resource_type=resource_type,
            **entry_overrides,
        ),
        context=_context(),
    )

    assert decision.action == "reconcile"
