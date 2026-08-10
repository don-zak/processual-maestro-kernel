from __future__ import annotations

from decimal import Decimal

from processual_api.admin_marketplace.activation_gate import (
    ActivationGateInput,
    evaluate_activation_gate,
)


def _candidate(**overrides: object) -> ActivationGateInput:
    values: dict[str, object] = {
        "order_ref": "order-local-001",
        "customer_ref": "customer-001",
        "offer_ref": "starter-monthly",
        "plan_ref": "starter",
        "order_status": "ready_for_activation",
        "contract_status": "completed",
        "payment_requirement": "required",
        "payment_status": "verified",
        "selected_channel": "maestro_direct",
        "country_code": "TN",
        "currency": "TND",
        "total_amount": Decimal("99.000"),
        "offer_snapshot": {
            "offer_ref": "starter-monthly",
            "plan_ref": "starter",
            "currency": "TND",
            "sales_channel": "maestro_direct",
            "snapshot_at": "2026-08-07T10:30:00+00:00",
        },
        "payment_customer_ref": "customer-001",
        "payment_order_ref": "order-local-001",
        "payment_amount": Decimal("99.000"),
        "payment_currency": "TND",
    }
    values.update(overrides)
    return ActivationGateInput(**values)


def test_local_offer_cannot_activate_before_payment_is_verified() -> None:
    decision = evaluate_activation_gate(
        _candidate(
            payment_status="reported",
            payment_customer_ref=None,
            payment_order_ref=None,
            payment_amount=None,
            payment_currency=None,
        )
    )

    assert decision.allowed is False
    assert "payment_not_verified" in decision.reasons
    assert "required_payment_not_verified" in decision.reasons


def test_verified_status_without_matching_settlement_evidence_fails_closed() -> None:
    decision = evaluate_activation_gate(
        _candidate(
            payment_customer_ref=None,
            payment_order_ref=None,
            payment_amount=None,
            payment_currency=None,
        )
    )

    assert decision.allowed is False
    assert "payment_customer_mismatch" in decision.reasons
    assert "payment_order_mismatch" in decision.reasons
    assert "payment_amount_mismatch" in decision.reasons
    assert "payment_currency_mismatch" in decision.reasons


def test_verified_matching_local_settlement_allows_offer_activation() -> None:
    decision = evaluate_activation_gate(_candidate())

    assert decision.allowed is True
    assert decision.reasons == ()


def test_local_payment_amount_must_match_authoritative_order_total() -> None:
    decision = evaluate_activation_gate(
        _candidate(payment_amount=Decimal("98.999"))
    )

    assert decision.allowed is False
    assert "payment_amount_mismatch" in decision.reasons
