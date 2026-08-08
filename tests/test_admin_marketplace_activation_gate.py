from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from processual_api.admin_marketplace.activation_gate import (
    ActivationGateInput,
    evaluate_activation_gate,
)


def _candidate() -> ActivationGateInput:
    return ActivationGateInput(
        order_ref="ord_safe_001",
        customer_ref="customer_alpha",
        offer_ref="pilot-pro-monthly-tn",
        plan_ref="pilot-pro",
        order_status="ready_for_activation",
        contract_status="completed",
        payment_requirement="required",
        payment_status="verified",
        selected_channel="maestro_direct",
        country_code="TN",
        currency="TND",
        total_amount=Decimal("300.000"),
        offer_snapshot={
            "offer_ref": "pilot-pro-monthly-tn",
            "plan_ref": "pilot-pro",
            "currency": "TND",
            "sales_channel": "maestro_direct",
            "snapshot_at": "2026-08-05T10:00:00+00:00",
        },
        payment_customer_ref="customer_alpha",
        payment_order_ref="ord_safe_001",
        payment_amount=Decimal("300.000"),
        payment_currency="TND",
    )


def test_complete_verified_direct_order_can_enter_activation() -> None:
    decision = evaluate_activation_gate(_candidate())

    assert decision.allowed is True
    assert decision.reasons == ()


def test_payment_from_another_customer_is_rejected() -> None:
    decision = evaluate_activation_gate(
        replace(_candidate(), payment_customer_ref="customer_beta")
    )

    assert decision.allowed is False
    assert "payment_customer_mismatch" in decision.reasons


def test_payment_for_another_order_is_rejected() -> None:
    decision = evaluate_activation_gate(
        replace(_candidate(), payment_order_ref="ord_other")
    )

    assert decision.allowed is False
    assert "payment_order_mismatch" in decision.reasons


def test_offer_or_plan_snapshot_tampering_is_rejected() -> None:
    tampered = dict(_candidate().offer_snapshot)
    tampered["offer_ref"] = "enterprise-annual"
    tampered["plan_ref"] = "enterprise"

    decision = evaluate_activation_gate(
        replace(_candidate(), offer_snapshot=tampered)
    )

    assert decision.allowed is False
    assert "offer_snapshot_mismatch" in decision.reasons
    assert "plan_snapshot_mismatch" in decision.reasons


def test_amount_and_currency_mismatch_are_rejected() -> None:
    decision = evaluate_activation_gate(
        replace(
            _candidate(),
            payment_amount=Decimal("299.000"),
            payment_currency="USD",
        )
    )

    assert decision.allowed is False
    assert "payment_amount_mismatch" in decision.reasons
    assert "payment_currency_mismatch" in decision.reasons


def test_unverified_required_payment_and_incomplete_contract_are_rejected() -> None:
    decision = evaluate_activation_gate(
        replace(
            _candidate(),
            order_status="awaiting_payment",
            contract_status="pending",
            payment_status="customer_reported",
            payment_customer_ref=None,
            payment_order_ref=None,
            payment_amount=None,
            payment_currency=None,
        )
    )

    assert decision.allowed is False
    assert "order_not_ready_for_activation" in decision.reasons
    assert "contract_not_completed" in decision.reasons
    assert "payment_not_verified" in decision.reasons
    assert "required_payment_not_verified" in decision.reasons


def test_direct_channel_cannot_activate_outside_tunisia_or_non_tnd() -> None:
    decision = evaluate_activation_gate(
        replace(_candidate(), country_code="FR", currency="EUR")
    )

    assert decision.allowed is False
    assert "direct_channel_requires_tunisia" in decision.reasons
    assert "direct_channel_requires_tnd" in decision.reasons
    assert "currency_snapshot_mismatch" in decision.reasons


def test_existing_subscription_blocks_duplicate_or_cross_account_activation() -> None:
    duplicate = evaluate_activation_gate(
        replace(
            _candidate(),
            existing_subscription_order_ref="ord_safe_001",
            existing_active_subscription_customer_ref="customer_alpha",
        )
    )
    cross_account = evaluate_activation_gate(
        replace(
            _candidate(),
            existing_active_subscription_customer_ref="customer_beta",
        )
    )

    assert duplicate.allowed is False
    assert "order_already_has_subscription" in duplicate.reasons
    assert "customer_already_has_active_subscription" in duplicate.reasons
    assert cross_account.allowed is False
    assert "active_subscription_customer_mismatch" in cross_account.reasons


def test_missing_snapshot_timestamp_fails_closed() -> None:
    snapshot = dict(_candidate().offer_snapshot)
    snapshot.pop("snapshot_at")

    decision = evaluate_activation_gate(
        replace(_candidate(), offer_snapshot=snapshot)
    )

    assert decision.allowed is False
    assert "missing_offer_snapshot_timestamp" in decision.reasons
