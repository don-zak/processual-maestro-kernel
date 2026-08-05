"""add fixed USD/TND commercial settlement fields

Revision ID: 20260729_0014
Revises: 20260729_0013
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0014"
down_revision: str | None = "20260729_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORDER_TABLE = "commercial_top_up_orders"
PAYMENT_TABLE = "commercial_top_up_payment_evidence"

ORDER_SETTLEMENT_CURRENCY_CHECK = "ck_commercial_top_up_orders_settlement_currency_allowed"
ORDER_SETTLEMENT_AMOUNT_CHECK = "ck_commercial_top_up_orders_settlement_amount_positive"
ORDER_CHANNEL_SETTLEMENT_CHECK = "ck_commercial_top_up_orders_channel_settlement_consistent"
PAYMENT_AMOUNT_CHECK = "ck_commercial_top_up_payment_evidence_verified_amount_positive"


def upgrade() -> None:
    with op.batch_alter_table(ORDER_TABLE) as batch_op:
        batch_op.add_column(
            sa.Column("settlement_currency", sa.String(length=3), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "settlement_amount",
                sa.Numeric(precision=18, scale=3),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "exchange_rate_usd_tnd",
                sa.Numeric(precision=18, scale=6),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("exchange_rate_source", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "exchange_rate_reference",
                sa.String(length=255),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "exchange_rate_observed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "exchange_rate_expires_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

    op.execute(
        sa.text(
            """
            UPDATE commercial_top_up_orders
            SET
                settlement_currency = 'USD',
                settlement_amount = total_price_usd
            WHERE settlement_currency IS NULL
               OR settlement_amount IS NULL
            """
        )
    )

    with op.batch_alter_table(ORDER_TABLE) as batch_op:
        batch_op.alter_column(
            "settlement_currency",
            existing_type=sa.String(length=3),
            nullable=False,
        )
        batch_op.alter_column(
            "settlement_amount",
            existing_type=sa.Numeric(precision=18, scale=3),
            nullable=False,
        )
        batch_op.create_check_constraint(
            op.f(ORDER_SETTLEMENT_CURRENCY_CHECK),
            "settlement_currency IN ('USD', 'TND')",
        )
        batch_op.create_check_constraint(
            op.f(ORDER_SETTLEMENT_AMOUNT_CHECK),
            "settlement_amount > 0",
        )
        batch_op.create_check_constraint(
            op.f(ORDER_CHANNEL_SETTLEMENT_CHECK),
            """
            (
                channel = 'lemon_squeezy'
                AND settlement_currency = 'USD'
                AND settlement_amount = total_price_usd
                AND exchange_rate_usd_tnd IS NULL
                AND exchange_rate_source IS NULL
                AND exchange_rate_reference IS NULL
                AND exchange_rate_observed_at IS NULL
                AND exchange_rate_expires_at IS NULL
            )
            OR
            (
                channel = 'local_tunisia'
                AND settlement_currency = 'TND'
                AND exchange_rate_usd_tnd IS NOT NULL
                AND exchange_rate_usd_tnd > 0
                AND exchange_rate_source IS NOT NULL
                AND length(trim(exchange_rate_source)) > 0
                AND exchange_rate_reference IS NOT NULL
                AND length(trim(exchange_rate_reference)) > 0
                AND exchange_rate_observed_at IS NOT NULL
                AND exchange_rate_expires_at IS NOT NULL
                AND exchange_rate_expires_at > exchange_rate_observed_at
            )
            """,
        )

    with op.batch_alter_table(PAYMENT_TABLE) as batch_op:
        batch_op.drop_constraint(op.f(PAYMENT_AMOUNT_CHECK), type_="check")
        batch_op.alter_column(
            "verified_amount_usd",
            new_column_name="verified_amount",
            existing_type=sa.Numeric(precision=18, scale=2),
            type_=sa.Numeric(precision=18, scale=3),
            existing_nullable=True,
        )
        batch_op.create_check_constraint(
            op.f(PAYMENT_AMOUNT_CHECK),
            "verified_amount IS NULL OR verified_amount > 0",
        )


def downgrade() -> None:
    with op.batch_alter_table(PAYMENT_TABLE) as batch_op:
        batch_op.drop_constraint(op.f(PAYMENT_AMOUNT_CHECK), type_="check")
        batch_op.alter_column(
            "verified_amount",
            new_column_name="verified_amount_usd",
            existing_type=sa.Numeric(precision=18, scale=3),
            type_=sa.Numeric(precision=18, scale=2),
            existing_nullable=True,
        )
        batch_op.create_check_constraint(
            op.f(PAYMENT_AMOUNT_CHECK),
            "verified_amount_usd IS NULL OR verified_amount_usd > 0",
        )

    with op.batch_alter_table(ORDER_TABLE) as batch_op:
        batch_op.drop_constraint(
            op.f(ORDER_CHANNEL_SETTLEMENT_CHECK),
            type_="check",
        )
        batch_op.drop_constraint(
            op.f(ORDER_SETTLEMENT_AMOUNT_CHECK),
            type_="check",
        )
        batch_op.drop_constraint(
            op.f(ORDER_SETTLEMENT_CURRENCY_CHECK),
            type_="check",
        )
        batch_op.drop_column("exchange_rate_expires_at")
        batch_op.drop_column("exchange_rate_observed_at")
        batch_op.drop_column("exchange_rate_reference")
        batch_op.drop_column("exchange_rate_source")
        batch_op.drop_column("exchange_rate_usd_tnd")
        batch_op.drop_column("settlement_amount")
        batch_op.drop_column("settlement_currency")
