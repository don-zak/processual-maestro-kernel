from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint

from processual_api.admin_marketplace.commercial_offer_provider_binding import (
    AdminMarketOfferProviderBinding,
    is_verified_lemon_squeezy_binding,
)

NOW = datetime(2026, 8, 17, 13, 30, tzinfo=UTC)
OFFER_ID = "offer-001"


def _binding(**changes: object) -> SimpleNamespace:
    values = {
        "offer_id": OFFER_ID,
        "provider": "lemon_squeezy",
        "provider_variant_id": "variant-001",
        "status": "verified",
        "verification_reference": "verify-001",
        "verified_at": NOW,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_provider_binding_is_channel_metadata_not_pricing_authority() -> None:
    columns = {
        column.name for column in AdminMarketOfferProviderBinding.__table__.columns
    }

    assert {
        "offer_id",
        "provider",
        "provider_variant_id",
        "status",
        "verification_reference",
        "verified_at",
    }.issubset(columns)
    assert columns.isdisjoint(
        {
            "amount",
            "price",
            "currency",
            "plan_code",
            "monthly_price",
            "annual_price",
            "quota_units",
        }
    )


def test_provider_binding_requires_one_offer_and_one_variant_identity() -> None:
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in AdminMarketOfferProviderBinding.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("offer_id",) in unique_columns
    assert ("provider_variant_id",) in unique_columns


def test_provider_binding_verification_state_is_database_constrained() -> None:
    checks = {
        str(constraint.sqltext)
        for constraint in AdminMarketOfferProviderBinding.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert any("lemon_squeezy" in expression for expression in checks)
    assert any(
        "pending" in expression
        and "verified" in expression
        and "revoked" in expression
        for expression in checks
    )
    assert any(
        "verification_reference" in expression and "verified_at" in expression
        for expression in checks
    )


def test_verified_binding_readiness_requires_complete_matching_identity() -> None:
    assert is_verified_lemon_squeezy_binding(
        _binding(),
        offer_id=OFFER_ID,
    ) is True


@pytest.mark.parametrize(
    ("changes", "offer_id"),
    [
        ({"offer_id": "offer-002"}, OFFER_ID),
        ({"provider": "other"}, OFFER_ID),
        ({"provider": None}, OFFER_ID),
        ({"status": "pending"}, OFFER_ID),
        ({"status": None}, OFFER_ID),
        ({"provider_variant_id": "   "}, OFFER_ID),
        ({"provider_variant_id": None}, OFFER_ID),
        ({"verification_reference": "   "}, OFFER_ID),
        ({"verification_reference": None}, OFFER_ID),
        ({"verified_at": None}, OFFER_ID),
    ],
)
def test_verified_binding_readiness_fails_closed(
    changes: dict[str, object],
    offer_id: object,
) -> None:
    assert is_verified_lemon_squeezy_binding(
        _binding(**changes),
        offer_id=offer_id,
    ) is False


def test_verified_binding_readiness_rejects_missing_binding() -> None:
    assert is_verified_lemon_squeezy_binding(None, offer_id=OFFER_ID) is False
