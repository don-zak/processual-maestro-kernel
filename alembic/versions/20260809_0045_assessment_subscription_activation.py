"""Add assessment-specific subscription activation bindings.

Revision ID: 20260809_0045
Revises: 20260809_0044
Create Date: 2026-08-09
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260809_0045"
down_revision: str | None = "20260809_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUBSCRIPTION_TABLE = "admin_market_subscriptions"
BINDING_TABLE = "admin_market_assessment_subscription_bindings"


def upgrade() -> None:
    with op.batch_alter_table(SUBSCRIPTION_TABLE) as batch_op:
        batch_op.alter_column(
            "offer_id",
            existing_type=sa.Uuid(),
            nullable=True,
        )

    op.create_table(
        BINDING_TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("binding_ref", sa.String(length=128), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_binding_hash", sa.String(length=64), nullable=False),
        sa.Column("assessment_id", sa.String(length=128), nullable=False),
        sa.Column("customer_ref", sa.String(length=128), nullable=False),
        sa.Column("public_plan_id", sa.String(length=128), nullable=False),
        sa.Column("entitlement_source_plan_code", sa.String(length=128), nullable=False),
        sa.Column("entitlement_plan_id", sa.Uuid(), nullable=False),
        sa.Column("entitlement_profile_ref", sa.String(length=128), nullable=False),
        sa.Column("quota_profile_ref", sa.String(length=128), nullable=False),
        sa.Column("activation_idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "length(assessment_binding_hash) = 64",
            name="assessment_binding_hash_length",
        ),
        sa.CheckConstraint(
            "length(activation_idempotency_key_hash) = 64",
            name="activation_idempotency_hash_length",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["admin_market_subscriptions.id"],
            name="fk_assessment_subscription_binding_subscription",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["entitlement_plan_id"],
            ["admin_market_plans.id"],
            name="fk_assessment_subscription_binding_plan",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["quota_profile_ref"],
            ["admin_market_assessment_quota_profiles.profile_ref"],
            name="fk_assessment_subscription_binding_quota_profile",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "binding_ref",
            name="uq_assessment_subscription_binding_ref",
        ),
        sa.UniqueConstraint(
            "subscription_id",
            name="uq_assessment_subscription_binding_subscription",
        ),
        sa.UniqueConstraint(
            "assessment_binding_hash",
            name="uq_assessment_subscription_binding_assessment_hash",
        ),
        sa.UniqueConstraint(
            "activation_idempotency_key_hash",
            name="uq_assessment_subscription_binding_idempotency_hash",
        ),
    )
    op.create_index(
        "ix_assessment_subscription_binding_customer",
        BINDING_TABLE,
        ["customer_ref", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        connection = op.get_bind()
        if connection.execute(sa.text(f"SELECT 1 FROM {BINDING_TABLE} LIMIT 1")).first():
            raise RuntimeError(
                "Downgrade blocked: assessment subscription activation bindings exist"
            )

    op.drop_index(
        "ix_assessment_subscription_binding_customer",
        table_name=BINDING_TABLE,
    )
    op.drop_table(BINDING_TABLE)
    with op.batch_alter_table(SUBSCRIPTION_TABLE) as batch_op:
        batch_op.alter_column(
            "offer_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )
