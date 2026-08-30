"""Extend audit vocabulary for payment-destination administration.

Revision ID: 20260804_0018
Revises: 20260804_0017
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy.sql.elements import conv

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


def _historical_constraint_name(name: str) -> conv:
    """Return the identifier actually produced by migration 0011.

    Migration 0011 supplied already-prefixed ``ck_<table>_...`` names while
    the repository naming convention was ``ck_%(table_name)s_%(constraint_name)s``.
    SQLAlchemy therefore produced a double-prefixed logical identifier.  Mark
    that historical identifier as converted so later batch operations do not
    apply the convention yet again; the dialect may still perform normal
    deterministic identifier truncation (notably PostgreSQL's 63-byte limit).
    """
    return conv(f"ck_{TABLE}_{name}")


def _replace_constraints(action_check: str, resource_check: str) -> None:
    action_name = _historical_constraint_name(ACTION_CONSTRAINT)
    resource_name = _historical_constraint_name(RESOURCE_CONSTRAINT)
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.drop_constraint(action_name, type_="check")
        batch_op.drop_constraint(resource_name, type_="check")
        batch_op.create_check_constraint(action_name, action_check)
        batch_op.create_check_constraint(resource_name, resource_check)


def upgrade() -> None:
    _replace_constraints(_ACTION_CHECK, _RESOURCE_CHECK)


def downgrade() -> None:
    _replace_constraints(_PREVIOUS_ACTION_CHECK, _PREVIOUS_RESOURCE_CHECK)
