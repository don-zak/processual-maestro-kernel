"""Add Tunisian Admin Marketplace payment destinations.

Revision ID: 20260804_0017
Revises: 20260804_0016
"""

import sqlalchemy as sa

from alembic import op

revision = "20260804_0017"
down_revision = "20260804_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_market_payment_destinations",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "destination_ref",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "display_name",
            sa.String(length=120),
            nullable=False,
        ),
        sa.Column(
            "destination_type",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "institution_name",
            sa.String(length=160),
            nullable=False,
        ),
        sa.Column(
            "account_holder_name",
            sa.String(length=160),
            nullable=False,
        ),
        sa.Column(
            "identifier_ciphertext",
            sa.LargeBinary(),
            nullable=False,
        ),
        sa.Column(
            "identifier_key_version",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "masked_identifier",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "country_code",
            sa.String(length=2),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
        ),
        sa.Column(
            "sales_channel",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
        ),
        sa.Column(
            "validation_method",
            sa.String(length=24),
            nullable=True,
        ),
        sa.Column(
            "validation_reason_code",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column(
            "validated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "effective_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "instructions",
            sa.String(length=1000),
            nullable=True,
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
            """
            destination_type IN (
                'bank_account',
                'postal_account'
            )
            """,
            name=op.f("ck_admin_market_payment_destinations_destination_type_allowed"),
        ),
        sa.CheckConstraint(
            "country_code = 'TN'",
            name=op.f("ck_admin_market_payment_destinations_country_tunisia_only"),
        ),
        sa.CheckConstraint(
            "currency = 'TND'",
            name=op.f("ck_admin_market_payment_destinations_currency_tnd_only"),
        ),
        sa.CheckConstraint(
            "sales_channel = 'maestro_direct'",
            name=op.f("ck_admin_market_payment_destinations_channel_direct"),
        ),
        sa.CheckConstraint(
            """
            status IN (
                'draft',
                'validated',
                'active',
                'inactive'
            )
            """,
            name=op.f("ck_admin_market_payment_destinations_status_allowed"),
        ),
        sa.CheckConstraint(
            """
            validation_method IS NULL
            OR validation_method IN (
                'structural',
                'provider'
            )
            """,
            name=op.f("ck_admin_market_payment_destinations_validation_method_allowed"),
        ),
        sa.CheckConstraint(
            "length(identifier_ciphertext) > 12",
            name=op.f("ck_admin_market_payment_destinations_ciphertext_not_truncated"),
        ),
        sa.CheckConstraint(
            "length(trim(masked_identifier)) >= 8",
            name=op.f("ck_admin_market_payment_destinations_masked_identifier_present"),
        ),
        sa.CheckConstraint(
            """
            expires_at IS NULL
            OR effective_at IS NULL
            OR expires_at > effective_at
            """,
            name=op.f("ck_admin_market_payment_destinations_effective_window_valid"),
        ),
        sa.CheckConstraint(
            """
            NOT is_active
            OR status = 'active'
            """,
            name=op.f("ck_admin_market_payment_destinations_active_status"),
        ),
        sa.CheckConstraint(
            """
            NOT is_default
            OR (
                is_active
                AND status = 'active'
            )
            """,
            name=op.f("ck_admin_market_payment_destinations_default_requires_active"),
        ),
        sa.CheckConstraint(
            """
            status = 'draft'
            OR (
                validation_method IS NOT NULL
                AND validation_reason_code IS NOT NULL
                AND validated_at IS NOT NULL
            )
            """,
            name=op.f("ck_admin_market_payment_destinations_validated_state"),
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_admin_market_payment_destinations",
        ),
        sa.UniqueConstraint(
            "destination_ref",
            name=(
                "uq_admin_market_payment_destinations_"
                "destination_ref"
            ),
        ),
    )

    op.create_index(
        "ix_admin_market_payment_destinations_status",
        "admin_market_payment_destinations",
        ["status", "is_active"],
        unique=False,
    )

    op.create_index(
        "uq_admin_market_payment_destinations_active_default",
        "admin_market_payment_destinations",
        ["sales_channel"],
        unique=True,
        postgresql_where=sa.text("is_active AND is_default"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_admin_market_payment_destinations_active_default",
        table_name="admin_market_payment_destinations",
    )
    op.drop_index(
        "ix_admin_market_payment_destinations_status",
        table_name="admin_market_payment_destinations",
    )
    op.drop_table("admin_market_payment_destinations")
