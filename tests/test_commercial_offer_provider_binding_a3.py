from __future__ import annotations

from sqlalchemy import CheckConstraint, UniqueConstraint

from processual_api.admin_marketplace.commercial_offer_provider_binding import (
    AdminMarketOfferProviderBinding,
)


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
