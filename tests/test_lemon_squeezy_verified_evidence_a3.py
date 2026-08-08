from __future__ import annotations

from datetime import UTC, datetime

import pytest

from processual_api.admin_marketplace.lemon_squeezy_evidence import (
    LemonSqueezyEvidenceError,
    extract_lemon_squeezy_verified_evidence,
)

EXPECTED_TIME = datetime(2026, 8, 6, 9, 30, tzinfo=UTC)


def test_order_evidence_captures_variant_money_and_provider_binding() -> None:
    evidence = extract_lemon_squeezy_verified_evidence(
        resource_type="orders",
        external_resource_id="6001",
        attributes={
            "customer_id": 5001,
            "status": "paid",
            "currency": "usd",
            "total": 1999,
            "updated_at": "2026-08-06T09:30:00Z",
            "first_order_item": {"variant_id": 8001},
        },
    )

    assert evidence.provider_customer_id == "5001"
    assert evidence.provider_order_id == "6001"
    assert evidence.provider_subscription_id is None
    assert evidence.variant_id == "8001"
    assert evidence.currency == "USD"
    assert evidence.total_amount == "1999"
    assert evidence.effective_at == EXPECTED_TIME


def test_subscription_evidence_captures_external_subscription_identity() -> None:
    evidence = extract_lemon_squeezy_verified_evidence(
        resource_type="subscriptions",
        external_resource_id="9001",
        attributes={
            "customer_id": 5001,
            "order_id": 6001,
            "variant_id": 8001,
            "status": "active",
            "updated_at": "2026-08-06T09:30:00+00:00",
        },
    )

    assert evidence.provider_order_id == "6001"
    assert evidence.provider_subscription_id == "9001"
    assert evidence.variant_id == "8001"
    assert evidence.currency is None
    assert evidence.total_amount is None


def test_invoice_evidence_captures_money_and_parent_subscription() -> None:
    evidence = extract_lemon_squeezy_verified_evidence(
        resource_type="subscription-invoices",
        external_resource_id="9101",
        attributes={
            "customer_id": 5001,
            "subscription_id": 9001,
            "status": "paid",
            "currency": "EUR",
            "total": "2499",
            "created_at": "2026-08-06T09:30:00Z",
        },
    )

    assert evidence.provider_subscription_id == "9001"
    assert evidence.provider_order_id is None
    assert evidence.variant_id is None
    assert evidence.currency == "EUR"
    assert evidence.total_amount == "2499"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("customer_id", True),
        ("updated_at", "2026-08-06T09:30:00"),
        ("variant_id", "not-an-id"),
    ],
)
def test_subscription_evidence_rejects_invalid_core_fields(
    field: str,
    value: object,
) -> None:
    attributes: dict[str, object] = {
        "customer_id": 5001,
        "order_id": 6001,
        "variant_id": 8001,
        "status": "active",
        "updated_at": "2026-08-06T09:30:00Z",
    }
    attributes[field] = value

    with pytest.raises(LemonSqueezyEvidenceError):
        extract_lemon_squeezy_verified_evidence(
            resource_type="subscriptions",
            external_resource_id="9001",
            attributes=attributes,
        )


def test_order_evidence_rejects_negative_amount() -> None:
    with pytest.raises(LemonSqueezyEvidenceError, match="total is invalid"):
        extract_lemon_squeezy_verified_evidence(
            resource_type="orders",
            external_resource_id="6001",
            attributes={
                "customer_id": 5001,
                "status": "paid",
                "currency": "USD",
                "total": -1,
                "updated_at": "2026-08-06T09:30:00Z",
                "first_order_item": {"variant_id": 8001},
            },
        )
