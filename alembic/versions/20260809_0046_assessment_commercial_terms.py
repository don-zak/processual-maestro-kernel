"""Persist approved commercial terms for assessment-based subscriptions.

Revision ID: 20260809_0046
Revises: 20260809_0045
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa

revision = "20260809_0046"
down_revision = "20260809_0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_market_assessment_commercial_terms",
        sa.Column("terms_ref", sa.String(length=128), nullable=False),
        sa.Column("assessment_binding_hash", sa.String(length=64), nullable=False),
        sa.Column("assessment_id", sa.String(length=128), nullable=False),
        sa.Column("customer_ref", sa.String(length=128), nullable=False),
        sa.Column("public_plan_id", sa.String(length=128), nullable=False),
        sa.Column("terms_version", sa.String(length=64), nullable=False),
        sa.Column("price_source", sa.String(length=24), nullable=False),
        sa.Column("source_reference", sa.String(length=128), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("billing_interval", sa.String(length=24), nullable=False),
        sa.Column("amount_minor_units", sa.BigInteger(), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=False),
        sa.Column("approval_reference", sa.String(length=128), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount_minor_units >= 0",
            name=op.f("ck_admin_market_assessment_commercial_terms_amount_nonnegative"),
        ),
        sa.CheckConstraint(
            "price_source IN ('assessment', 'contract')",
            name=op.f("ck_admin_market_assessment_commercial_terms_price_source_allowed"),
        ),
        sa.CheckConstraint(
            "length(currency) = 3",
            name=op.f("ck_admin_market_assessment_commercial_terms_currency_length"),
        ),
        sa.CheckConstraint(
            "billing_interval IN ('monthly', 'annual', 'one_time', 'custom')",
            name=op.f("ck_admin_market_assessment_commercial_terms_billing_interval_allowed"),
        ),
        sa.CheckConstraint(
            "length(payload_digest) = 64",
            name=op.f("ck_admin_market_assessment_commercial_terms_payload_digest_length"),
        ),
        sa.ForeignKeyConstraint(
            ["assessment_binding_hash"],
            ["admin_market_assessment_quota_profiles.assessment_binding_hash"],
            name="fk_admin_market_assessment_terms_binding_hash",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "terms_ref",
            name="pk_admin_market_assessment_commercial_terms",
        ),
        sa.UniqueConstraint(
            "assessment_binding_hash",
            name="uq_admin_market_assessment_commercial_terms_binding_hash",
        ),
        sa.UniqueConstraint(
            "approval_reference",
            name="uq_admin_market_assessment_commercial_terms_approval_reference",
        ),
    )
    op.create_index(
        "ix_admin_market_assessment_commercial_terms_customer",
        "admin_market_assessment_commercial_terms",
        ["customer_ref", "public_plan_id"],
        unique=False,
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        row = bind.execute(
            sa.text(
                "SELECT terms_ref FROM admin_market_assessment_commercial_terms LIMIT 1"
            )
        ).first()
        if row is not None:
            raise RuntimeError(
                "Downgrade blocked: assessment commercial terms bindings exist"
            )

    op.drop_index(
        "ix_admin_market_assessment_commercial_terms_customer",
        table_name="admin_market_assessment_commercial_terms",
    )
    op.drop_table("admin_market_assessment_commercial_terms")
