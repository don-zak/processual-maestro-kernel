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
    op.add_column(
        ORDER_TABLE,
        sa.Column(
            "settlement_currency",
            sa.String(length=3),
            nullable=True,
        ),
    )
    op.add_column(
        ORDER_TABLE,
        sa.Column(
            "settlement_amount",
            sa.Numeric(precision=18, scale=3),
            nullable=True,
        ),
    )
    op.add_column(
        ORDER_TABLE,
        sa.Column(
            "exchange_rate_usd_tnd",
            sa.Numeric(precision=18, scale=6),
            nullable=True,
        ),
    )
    op.add_column(
        ORDER_TABLE,
        sa.Column(
            "exchange_rate_source",
            sa.String(length=255),
            nullable=True,
        ),
    )
    op.add_column(
        ORDER_TABLE,
        sa.Column(
            "exchange_rate_reference",
            sa.String(length=255),
            nullable=True,
        ),
    )
    op.add_column(
        ORDER_TABLE,
        sa.Column(
            "exchange_rate_observed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        ORDER_TABLE,
        sa.Column(
            "exchange_rate_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
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

    op.alter_column(
        ORDER_TABLE,
        "settlement_currency",
        existing_type=sa.String(length=3),
        nullable=False,
    )
    op.alter_column(
        ORDER_TABLE,
        "settlement_amount",
        existing_type=sa.Numeric(precision=18, scale=3),
        nullable=False,
    )

    op.create_check_constraint(
        ORDER_SETTLEMENT_CURRENCY_CHECK,
        ORDER_TABLE,
        "settlement_currency IN ('USD', 'TND')",
    )
    op.create_check_constraint(
        ORDER_SETTLEMENT_AMOUNT_CHECK,
        ORDER_TABLE,
        "settlement_amount > 0",
    )
    op.create_check_constraint(
        ORDER_CHANNEL_SETTLEMENT_CHECK,
        ORDER_TABLE,
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
            AND exchange_rate_expires_at
                > exchange_rate_observed_at
        )
        """,
    )

    op.drop_constraint(
        op.f(PAYMENT_AMOUNT_CHECK),
        PAYMENT_TABLE,
        type_="check",
    )
    op.alter_column(
        PAYMENT_TABLE,
        "verified_amount_usd",
        new_column_name="verified_amount",
        existing_type=sa.Numeric(precision=18, scale=2),
        type_=sa.Numeric(precision=18, scale=3),
        existing_nullable=True,
    )
    op.create_check_constraint(
        op.f(PAYMENT_AMOUNT_CHECK),
        PAYMENT_TABLE,
        "verified_amount IS NULL OR verified_amount > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f(PAYMENT_AMOUNT_CHECK),
        PAYMENT_TABLE,
        type_="check",
    )
    op.alter_column(
        PAYMENT_TABLE,
        "verified_amount",
        new_column_name="verified_amount_usd",
        existing_type=sa.Numeric(precision=18, scale=3),
        type_=sa.Numeric(precision=18, scale=2),
        existing_nullable=True,
    )
    op.create_check_constraint(
        op.f(PAYMENT_AMOUNT_CHECK),
        PAYMENT_TABLE,
        "verified_amount_usd IS NULL OR verified_amount_usd > 0",
    )

    op.drop_constraint(
        ORDER_CHANNEL_SETTLEMENT_CHECK,
        ORDER_TABLE,
        type_="check",
    )
    op.drop_constraint(
        ORDER_SETTLEMENT_AMOUNT_CHECK,
        ORDER_TABLE,
        type_="check",
    )
    op.drop_constraint(
        ORDER_SETTLEMENT_CURRENCY_CHECK,
        ORDER_TABLE,
        type_="check",
    )

    op.drop_column(ORDER_TABLE, "exchange_rate_expires_at")
    op.drop_column(ORDER_TABLE, "exchange_rate_observed_at")
    op.drop_column(ORDER_TABLE, "exchange_rate_reference")
    op.drop_column(ORDER_TABLE, "exchange_rate_source")
    op.drop_column(ORDER_TABLE, "exchange_rate_usd_tnd")
    op.drop_column(ORDER_TABLE, "settlement_amount")
    op.drop_column(ORDER_TABLE, "settlement_currency")
