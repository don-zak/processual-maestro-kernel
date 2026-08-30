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

TABLE = "admin_market_audit_records"
ACTION_CONSTRAINT = "ck_admin_market_audit_records_action_allowed"
RESOURCE_CONSTRAINT = "ck_admin_market_audit_records_resource_type_allowed"

_ACTION_CHECK = """action IN (
    'authority_checked', 'offer_decided', 'channel_eligibility_decided',
    'channel_selected', 'payment_verification_decided',
    'subscription_activation_decided', 'payment_destination_created',
    'payment_destination_validated', 'payment_destination_activated',
    'payment_destination_deactivated', 'payment_destination_default_set'
)"""
_PREVIOUS_ACTION_CHECK = """action IN (
    'authority_checked', 'offer_decided', 'channel_eligibility_decided',
    'channel_selected', 'payment_verification_decided',
    'subscription_activation_decided'
)"""
_RESOURCE_CHECK = """resource_type IN (
    'offer', 'plan', 'order', 'payment_verification', 'subscription', 'trial',
    'sales_channel_eligibility', 'payment_destination'
)"""
_PREVIOUS_RESOURCE_CHECK = """resource_type IN (
    'offer', 'plan', 'order', 'payment_verification', 'subscription', 'trial',
    'sales_channel_eligibility'
)"""


def _replace_constraints(action_check: str, resource_check: str) -> None:
    # These constants are already fully rendered historical identifiers. Mark
    # them final so the repository naming convention does not prefix them again
    # during batch-mode drop/create operations (notably SQLite rebuilds and
    # PostgreSQL full downgrade qualification).
    action_name = op.f(ACTION_CONSTRAINT)
    resource_name = op.f(RESOURCE_CONSTRAINT)
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.drop_constraint(action_name, type_="check")
        batch_op.drop_constraint(resource_name, type_="check")
        batch_op.create_check_constraint(action_name, action_check)
        batch_op.create_check_constraint(resource_name, resource_check)


def upgrade() -> None:
    _replace_constraints(_ACTION_CHECK, _RESOURCE_CHECK)


def downgrade() -> None:
    _replace_constraints(_PREVIOUS_ACTION_CHECK, _PREVIOUS_RESOURCE_CHECK)
