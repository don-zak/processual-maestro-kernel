from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from processual_api.admin_marketplace.contracts import (
    CommercialOfferContract,
    CommercialPlanContract,
    CommercialSubscriptionContract,
    OfferStatus,
    SubscriptionStatus,
)
from processual_api.admin_marketplace.errors import AdminMarketplaceError


def test_contracts_are_immutable_and_separate_plan_offer_subscription() -> None:
    plan = CommercialPlanContract(
        plan_code="pilot_pro",
        display_name="Pilot Pro",
        entitlement_profile_ref="entitlement.pilot_pro",
        quota_profile_ref="quota.pilot_pro",
    )
    offer = CommercialOfferContract(
        offer_code="pilot_pro_monthly",
        plan_code=plan.plan_code,
        display_name="Pilot Pro Monthly",
        currency="USD",
        amount=Decimal("199.00"),
    )
    subscription = CommercialSubscriptionContract(
        subscription_id="sub_001",
        customer_id="customer_001",
        offer_code=offer.offer_code,
        plan_code=plan.plan_code,
        status=SubscriptionStatus.PENDING,
    )

    assert offer.status is OfferStatus.DRAFT
    assert subscription.status is SubscriptionStatus.PENDING
    assert plan.plan_code != offer.offer_code

    with pytest.raises(FrozenInstanceError):
        offer.status = OfferStatus.PUBLISHED  # type: ignore[misc]


def test_offer_rejects_negative_amount_and_invalid_period() -> None:
    with pytest.raises(AdminMarketplaceError, match="amount"):
        CommercialOfferContract(
            offer_code="offer_01",
            plan_code="plan_01",
            display_name="Offer",
            currency="USD",
            amount=Decimal("-1"),
        )

    now = datetime.now(UTC)
    with pytest.raises(AdminMarketplaceError, match="expires_at"):
        CommercialOfferContract(
            offer_code="offer_01",
            plan_code="plan_01",
            display_name="Offer",
            currency="TND",
            amount=Decimal("10"),
            effective_at=now,
            expires_at=now - timedelta(seconds=1),
        )


def test_metadata_is_immutable() -> None:
    plan = CommercialPlanContract(
        plan_code="plan_01",
        display_name="Plan",
        entitlement_profile_ref="entitlement.plan_01",
        quota_profile_ref="quota.plan_01",
        metadata={"source": "draft_review"},
    )
    with pytest.raises(TypeError):
        plan.metadata["source"] = "approved"  # type: ignore[index]


def test_unknown_status_and_non_finite_amount_are_rejected() -> None:
    with pytest.raises(AdminMarketplaceError, match="valid OfferStatus"):
        CommercialOfferContract(
            offer_code="offer_01",
            plan_code="plan_01",
            display_name="Offer",
            currency="USD",
            amount=Decimal("1"),
            status="published_typo",  # type: ignore[arg-type]
        )

    for amount in (
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ):
        with pytest.raises(AdminMarketplaceError, match="finite"):
            CommercialOfferContract(
                offer_code="offer_01",
                plan_code="plan_01",
                display_name="Offer",
                currency="USD",
                amount=amount,
            )
