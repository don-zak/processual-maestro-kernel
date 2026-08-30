"""Persist immutable provenance for commercial channel offers.

Revision ID: 20260817_0047
Revises: 20260809_0046
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "20260817_0047"
down_revision = "20260809_0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_market_offer_provenance",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("offer_id", sa.Uuid(), nullable=False),
        sa.Column("provenance_version", sa.String(length=64), nullable=False),
        sa.Column("source_pricing_version", sa.String(length=64), nullable=False),
        sa.Column("source_pricebook_version", sa.String(length=64), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("evidence_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(evidence_sha256) = 64",
            name=op.f("ck_admin_market_offer_provenance_digest_length"),
        ),
        sa.ForeignKeyConstraint(
            ["offer_id"],
            ["admin_market_offers.id"],
            name="fk_admin_market_offer_provenance_offer",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_admin_market_offer_provenance",
        ),
        sa.UniqueConstraint(
            "offer_id",
            name="uq_admin_market_offer_provenance_offer_id",
        ),
        sa.UniqueConstraint(
            "evidence_sha256",
            name="uq_admin_market_offer_provenance_digest",
        ),
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        row = bind.execute(
            sa.text("SELECT id FROM admin_market_offer_provenance LIMIT 1")
        ).first()
        if row is not None:
            raise RuntimeError(
                "Downgrade blocked: commercial offer provenance records exist"
            )

    op.drop_table("admin_market_offer_provenance")
