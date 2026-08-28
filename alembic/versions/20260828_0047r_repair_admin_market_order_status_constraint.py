"""Repair legacy Admin Marketplace order status constraint overlap.

Revision ID: 20260828_0047r
Revises: 20260809_0046

This reconciliation migration intentionally rebases the qualified 0058 repair
onto the current release-authority migration head. It does not import the
unreconciled 0047-0057 historical chain.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260828_0047r"
down_revision: str | None = "20260809_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "admin_market_orders"
_CANONICAL_NAME = "ck_admin_market_orders_status_allowed"
_LEGACY_DOUBLE_NAME = "ck_admin_market_orders_ck_admin_market_orders_status_allowed"
_CURRENT_STATUS = """status IN (
'draft','awaiting_contract','awaiting_payment','payment_under_review',
'ready_for_activation','activated','cancelled','expired','requires_review')"""
_PREVIOUS_STATUS = """status IN (
'draft','submitted','awaiting_payment_verification','approved','rejected',
'cancelled','fulfilled')"""


def _check_names() -> set[str]:
    if context.is_offline_mode():
        return {_CANONICAL_NAME, _LEGACY_DOUBLE_NAME}
    inspector = sa.inspect(op.get_bind())
    return {
        item["name"]
        for item in inspector.get_check_constraints(_TABLE)
        if item.get("name")
    }


def _drop_status_constraints() -> None:
    existing = _check_names()
    with op.batch_alter_table(_TABLE) as batch_op:
        for name in (_CANONICAL_NAME, _LEGACY_DOUBLE_NAME):
            if name in existing:
                batch_op.drop_constraint(op.f(name), type_="check")


def upgrade() -> None:
    _drop_status_constraints()
    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.create_check_constraint(op.f(_CANONICAL_NAME), _CURRENT_STATUS)


def downgrade() -> None:
    existing = _check_names()
    with op.batch_alter_table(_TABLE) as batch_op:
        if _CANONICAL_NAME in existing:
            batch_op.drop_constraint(op.f(_CANONICAL_NAME), type_="check")
        if _LEGACY_DOUBLE_NAME in existing:
            batch_op.drop_constraint(op.f(_LEGACY_DOUBLE_NAME), type_="check")

    if not context.is_offline_mode():
        bind = op.get_bind()
        incompatible = bind.execute(
            sa.text(
                "SELECT 1 FROM admin_market_orders "
                "WHERE status NOT IN ('draft','cancelled') LIMIT 1"
            )
        ).first()
        if incompatible:
            raise RuntimeError(
                "Downgrade blocked: current order statuses cannot safely restore "
                "the overlapping legacy constraint."
            )

    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.create_check_constraint(op.f(_CANONICAL_NAME), _CURRENT_STATUS)
        batch_op.create_check_constraint(op.f(_LEGACY_DOUBLE_NAME), _PREVIOUS_STATUS)
