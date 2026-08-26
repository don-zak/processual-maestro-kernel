"""Bind canonical commercial offers to verified provider variants.

Revision ID: 20260817_0048
Revises: 20260817_0047
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "20260817_0048"
down_revision = "20260817_0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_market_offer_provider_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("offer_id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider",
            sa.String(length=32),
            server_default="lemon_squeezy",
            nullable=False,
        ),
        sa.Column("provider_variant_id", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            sa.String(length=24),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("verification_reference", sa.String(length=128), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider = 'lemon_squeezy'",
            name=op.f("ck_admin_market_offer_provider_bindings_provider_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'verified', 'revoked')",
            name=op.f("ck_admin_market_offer_provider_bindings_status_allowed"),
        ),
        sa.CheckConstraint(
            """
            (status = 'pending' AND verification_reference IS NULL AND verified_at IS NULL)
            OR
            (status IN ('verified', 'revoked') AND verification_reference IS NOT NULL AND verified_at IS NOT NULL)
            """,
            name=op.f(
                "ck_admin_market_offer_provider_bindings_verification_state_consistent"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["offer_id"],
            ["admin_market_offers.id"],
            name="fk_admin_market_offer_provider_binding_offer",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_admin_market_offer_provider_bindings",
        ),
        sa.UniqueConstraint(
            "offer_id",
            name="uq_admin_market_offer_provider_binding_offer",
        ),
        sa.UniqueConstraint(
            "provider_variant_id",
            name="uq_admin_market_offer_provider_binding_variant",
        ),
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        row = bind.execute(
            sa.text("SELECT id FROM admin_market_offer_provider_bindings LIMIT 1")
        ).first()
        if row is not None:
            raise RuntimeError(
                "Downgrade blocked: commercial offer provider bindings exist"
            )

    op.drop_table("admin_market_offer_provider_bindings")
