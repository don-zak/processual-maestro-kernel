"""add commercial entitlement ledger persistence

Revision ID: 20260730_0015
Revises: 20260729_0014
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260730_0015"
down_revision: str | None = "20260729_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


LEDGER_TABLE = "commercial_entitlement_ledger_entries"
BALANCE_TABLE = "commercial_entitlement_balances"
RESERVATION_LOCK_TABLE = "commercial_entitlement_reservation_locks"


def upgrade() -> None:
    op.create_table(
        LEDGER_TABLE,
        sa.Column("entry_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column(
            "entry_type",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("units", sa.BigInteger(), nullable=False),
        sa.Column(
            "idempotency_key",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "source_reference",
            sa.String(length=512),
            nullable=False,
        ),
        sa.Column(
            "reservation_id",
            sa.Uuid(),
            nullable=True,
        ),
        sa.Column(
            "related_entry_id",
            sa.Uuid(),
            nullable=True,
        ),
        sa.Column(
            "adjustment_units",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "entry_id",
            name="pk_commercial_entitlement_ledger_entries",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "subscription_id",
            "idempotency_key",
            name=("uq_commercial_entitlement_ledger_entries_scope_idempotency"),
        ),
        sa.CheckConstraint(
            "units > 0",
            name=("ck_commercial_entitlement_ledger_entries_units_positive"),
        ),
        sa.ForeignKeyConstraint(
            ("related_entry_id",),
            ("commercial_entitlement_ledger_entries.entry_id",),
            name=("fk_commercial_entitlement_ledger_entries_related_entry"),
            ondelete="RESTRICT",
        ),
    )

    op.create_index(
        "ix_commercial_entitlement_ledger_entries_scope_occurred",
        LEDGER_TABLE,
        (
            "tenant_id",
            "subscription_id",
            "occurred_at",
        ),
        unique=False,
    )
    op.create_index(
        "ix_commercial_entitlement_ledger_entries_reservation",
        LEDGER_TABLE,
        (
            "tenant_id",
            "subscription_id",
            "reservation_id",
        ),
        unique=False,
        postgresql_where=sa.text("reservation_id IS NOT NULL"),
    )
    op.create_index(
        "ix_commercial_entitlement_ledger_entries_related_entry",
        LEDGER_TABLE,
        ("related_entry_id",),
        unique=False,
        postgresql_where=sa.text("related_entry_id IS NOT NULL"),
    )

    op.create_table(
        BALANCE_TABLE,
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column(
            "available_units",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "reserved_units",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "committed_units",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "version",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "tenant_id",
            "subscription_id",
            name="pk_commercial_entitlement_balances",
        ),
        sa.CheckConstraint(
            "available_units >= 0",
            name=("ck_commercial_entitlement_balances_available_nonnegative"),
        ),
        sa.CheckConstraint(
            "reserved_units >= 0",
            name=("ck_commercial_entitlement_balances_reserved_nonnegative"),
        ),
        sa.CheckConstraint(
            "committed_units >= 0",
            name=("ck_commercial_entitlement_balances_committed_nonnegative"),
        ),
        sa.CheckConstraint(
            "version >= 0",
            name=("ck_commercial_entitlement_balances_version_nonnegative"),
        ),
    )

    op.create_index(
        "ix_commercial_entitlement_balances_subscription",
        BALANCE_TABLE,
        ("subscription_id",),
        unique=False,
    )

    op.create_table(
        RESERVATION_LOCK_TABLE,
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("reservation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "owner_token",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "tenant_id",
            "subscription_id",
            "reservation_id",
            name=("pk_commercial_entitlement_reservation_locks"),
        ),
        sa.CheckConstraint(
            "length(trim(owner_token)) > 0",
            name=("ck_commercial_entitlement_reservation_locks_owner_nonblank"),
        ),
    )

    op.create_index(
        "ix_commercial_entitlement_reservation_locks_expires",
        RESERVATION_LOCK_TABLE,
        ("expires_at",),
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_commercial_entitlement_reservation_locks_expires",
        table_name=RESERVATION_LOCK_TABLE,
    )
    op.drop_table(RESERVATION_LOCK_TABLE)

    op.drop_index(
        "ix_commercial_entitlement_balances_subscription",
        table_name=BALANCE_TABLE,
    )
    op.drop_table(BALANCE_TABLE)

    op.drop_index(
        "ix_commercial_entitlement_ledger_entries_related_entry",
        table_name=LEDGER_TABLE,
    )
    op.drop_index(
        "ix_commercial_entitlement_ledger_entries_reservation",
        table_name=LEDGER_TABLE,
    )
    op.drop_index(
        "ix_commercial_entitlement_ledger_entries_scope_occurred",
        table_name=LEDGER_TABLE,
    )
    op.drop_table(LEDGER_TABLE)
