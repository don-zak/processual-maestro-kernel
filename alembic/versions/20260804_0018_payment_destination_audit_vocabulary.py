"""Extend audit vocabulary for payment-destination administration.

Revision ID: 20260804_0018
Revises: 20260804_0017
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260804_0018"
down_revision: str | None = "20260804_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_ACTION_CHECK = """
action IN (
    'authority_checked',
    'offer_decided',
    'channel_eligibility_decided',
    'channel_selected',
    'payment_verification_decided',
    'subscription_activation_decided',
    'payment_destination_created',
    'payment_destination_validated',
    'payment_destination_activated',
    'payment_destination_deactivated',
    'payment_destination_default_set'
)
"""

_PREVIOUS_ACTION_CHECK = """
action IN (
    'authority_checked',
    'offer_decided',
    'channel_eligibility_decided',
    'channel_selected',
    'payment_verification_decided',
    'subscription_activation_decided'
)
"""

_RESOURCE_CHECK = """
resource_type IN (
    'offer',
    'plan',
    'order',
    'payment_verification',
    'subscription',
    'trial',
    'sales_channel_eligibility',
    'payment_destination'
)
"""

_PREVIOUS_RESOURCE_CHECK = """
resource_type IN (
    'offer',
    'plan',
    'order',
    'payment_verification',
    'subscription',
    'trial',
    'sales_channel_eligibility'
)
"""


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_admin_market_audit_records_action_allowed"),
        "admin_market_audit_records",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_admin_market_audit_records_resource_type_allowed"),
        "admin_market_audit_records",
        type_="check",
    )

    op.create_check_constraint(
        op.f("ck_admin_market_audit_records_action_allowed"),
        "admin_market_audit_records",
        _ACTION_CHECK,
    )
    op.create_check_constraint(
        op.f("ck_admin_market_audit_records_resource_type_allowed"),
        "admin_market_audit_records",
        _RESOURCE_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_admin_market_audit_records_resource_type_allowed"),
        "admin_market_audit_records",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_admin_market_audit_records_action_allowed"),
        "admin_market_audit_records",
        type_="check",
    )

    op.create_check_constraint(
        op.f("ck_admin_market_audit_records_action_allowed"),
        "admin_market_audit_records",
        _PREVIOUS_ACTION_CHECK,
    )
    op.create_check_constraint(
        op.f("ck_admin_market_audit_records_resource_type_allowed"),
        "admin_market_audit_records",
        _PREVIOUS_RESOURCE_CHECK,
    )
