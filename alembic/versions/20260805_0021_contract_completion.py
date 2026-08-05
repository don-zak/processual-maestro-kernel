"""Add immutable direct-order contract completion records.

Revision ID: 20260805_0021
Revises: 20260804_0020
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260805_0021"
down_revision: str | None = "20260804_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUDIT_ACTIONS = """
action IN (
    'authority_checked',
    'offer_decided',
    'channel_eligibility_decided',
    'channel_selected',
    'payment_verification_decided',
    'subscription_activation_decided',
    'payment_destination_created',
    'payment_destination_validated',
    'payment_destination_activated',
    'payment_destination_deactivated',
    'payment_destination_default_set',
    'order_created',
    'contract_completed'
)
"""

_PREVIOUS_AUDIT_ACTIONS = """
action IN (
    'authority_checked',
    'offer_decided',
    'channel_eligibility_decided',
    'channel_selected',
    'payment_verification_decided',
    'subscription_activation_decided',
    'payment_destination_created',
    'payment_destination_validated',
    'payment_destination_activated',
    'payment_destination_deactivated',
    'payment_destination_default_set',
    'order_created'
)
"""


def upgrade() -> None:
    op.create_table(
        "admin_market_contracts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contract_ref", sa.String(length=128), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("customer_ref", sa.String(length=128), nullable=False),
        sa.Column("contract_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("accepted_party_ref", sa.String(length=128), nullable=False),
        sa.Column("acceptance_method", sa.String(length=32), nullable=False),
        sa.Column("evidence_reference", sa.String(length=128), nullable=False),
        sa.Column(
            "completion_idempotency_key_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'rejected', 'expired')",
            name=op.f("ck_admin_market_contracts_status_allowed"),
        ),
        sa.CheckConstraint(
            "acceptance_method IN ('authenticated_clickwrap', 'admin_exception')",
            name=op.f("ck_admin_market_contracts_acceptance_method_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["admin_market_orders.id"],
            name=op.f("fk_admin_market_contracts_order_id_admin_market_orders"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_market_contracts")),
        sa.UniqueConstraint(
            "contract_ref",
            name=op.f("uq_admin_market_contracts_contract_ref"),
        ),
        sa.UniqueConstraint(
            "order_id",
            name=op.f("uq_admin_market_contracts_order_id"),
        ),
        sa.UniqueConstraint(
            "evidence_reference",
            name=op.f("uq_admin_market_contracts_evidence_reference"),
        ),
        sa.UniqueConstraint(
            "completion_idempotency_key_hash",
            name=op.f("uq_admin_market_contracts_completion_idem_hash"),
        ),
    )
    op.create_index(
        op.f("ix_admin_market_contracts_customer_status"),
        "admin_market_contracts",
        ["customer_ref", "status"],
        unique=False,
    )
    op.drop_constraint(
        op.f("ck_admin_market_audit_records_action_allowed"),
        "admin_market_audit_records",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_admin_market_audit_records_action_allowed"),
        "admin_market_audit_records",
        _AUDIT_ACTIONS,
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM admin_market_contracts)
               OR EXISTS (
                    SELECT 1 FROM admin_market_audit_records
                    WHERE action = 'contract_completed'
               )
            THEN
                RAISE EXCEPTION
                    'Downgrade blocked: completed commercial contract exists';
            END IF;
        END $$
        """
    )
    op.drop_constraint(
        op.f("ck_admin_market_audit_records_action_allowed"),
        "admin_market_audit_records",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_admin_market_audit_records_action_allowed"),
        "admin_market_audit_records",
        _PREVIOUS_AUDIT_ACTIONS,
    )
    op.drop_index(
        op.f("ix_admin_market_contracts_customer_status"),
        table_name="admin_market_contracts",
    )
    op.drop_table("admin_market_contracts")
