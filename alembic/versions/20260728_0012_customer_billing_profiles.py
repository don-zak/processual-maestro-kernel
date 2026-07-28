# ruff: noqa: E501
"""Add authoritative customer billing profiles.

Revision ID: 20260728_0012
Revises: 20260727_0011
"""

import sqlalchemy as sa

from alembic import op

revision = "20260728_0012"
down_revision = "20260727_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_billing_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("region", sa.String(length=160), nullable=True),
        sa.Column("city", sa.String(length=160), nullable=True),
        sa.Column("postal_code", sa.String(length=32), nullable=True),
        sa.Column("address_line_1", sa.String(length=300), nullable=True),
        sa.Column("address_line_2", sa.String(length=300), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
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
            "country_code = upper(country_code) AND length(country_code) = 2",
            name="ck_customer_billing_profiles_country_code_format",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'review_required', 'disabled')",
            name="ck_customer_billing_profiles_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["identity_organizations.id"],
            name=(
                "fk_customer_billing_profiles_organization"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name="fk_customer_billing_profiles_user_id_identity_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_customer_billing_profiles",
        ),
    )

    op.create_index(
        "uq_customer_billing_profiles_personal",
        "customer_billing_profiles",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("organization_id IS NULL"),
    )
    op.create_index(
        "uq_customer_billing_profiles_organization",
        "customer_billing_profiles",
        ["user_id", "organization_id"],
        unique=True,
        postgresql_where=sa.text("organization_id IS NOT NULL"),
    )
    op.create_index(
        "ix_customer_billing_profiles_country_status",
        "customer_billing_profiles",
        ["country_code", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_customer_billing_profiles_country_status",
        table_name="customer_billing_profiles",
    )
    op.drop_index(
        "uq_customer_billing_profiles_organization",
        table_name="customer_billing_profiles",
    )
    op.drop_index(
        "uq_customer_billing_profiles_personal",
        table_name="customer_billing_profiles",
    )
    op.drop_table("customer_billing_profiles")
