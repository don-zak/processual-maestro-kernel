"""Add safe payment evidence matching and administrator verification.

Revision ID: 20260805_0022
Revises: 20260805_0021
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260805_0022"
down_revision: str | None = "20260805_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUDIT_ACTIONS = """
action IN (
    'authority_checked', 'offer_decided', 'channel_eligibility_decided',
    'channel_selected', 'payment_verification_decided',
    'subscription_activation_decided', 'payment_destination_created',
    'payment_destination_validated', 'payment_destination_activated',
    'payment_destination_deactivated', 'payment_destination_default_set',
    'order_created', 'contract_completed', 'payment_evidence_recorded'
)
"""

_PREVIOUS_AUDIT_ACTIONS = """
action IN (
    'authority_checked', 'offer_decided', 'channel_eligibility_decided',
    'channel_selected', 'payment_verification_decided',
    'subscription_activation_decided', 'payment_destination_created',
    'payment_destination_validated', 'payment_destination_activated',
    'payment_destination_deactivated', 'payment_destination_default_set',
    'order_created', 'contract_completed'
)
"""

_AUDIT_RESOURCES = """
resource_type IN (
    'offer', 'plan', 'order', 'payment_verification', 'subscription', 'trial',
    'sales_channel_eligibility', 'payment_destination', 'contract',
    'payment_evidence'
)
"""

_PREVIOUS_AUDIT_RESOURCES = """
resource_type IN (
    'offer', 'plan', 'order', 'payment_verification', 'subscription', 'trial',
    'sales_channel_eligibility', 'payment_destination'
)
"""


def upgrade() -> None:
    op.create_table(
        "admin_market_payment_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evidence_ref", sa.String(length=128), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("customer_ref", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("actual_amount", sa.Numeric(18, 3), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("safe_source_reference", sa.String(length=128), nullable=False),
        sa.Column("source_reference_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "submission_idempotency_key_hash", sa.String(length=64), nullable=False
        ),
        sa.Column("reference_matched", sa.Boolean(), nullable=False),
        sa.Column("amount_matched", sa.Boolean(), nullable=False),
        sa.Column("currency_matched", sa.Boolean(), nullable=False),
        sa.Column("destination_matched", sa.Boolean(), nullable=False),
        sa.Column("match_reason_code", sa.String(length=128), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_type IN ('customer_report', 'admin_exception', 'provider_notification', 'reconciliation')",
            name=op.f("ck_admin_market_payment_evidence_source_type_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('received', 'matched', 'requires_review', 'rejected')",
            name=op.f("ck_admin_market_payment_evidence_status_allowed"),
        ),
        sa.CheckConstraint(
            "actual_amount >= 0",
            name=op.f("ck_admin_market_payment_evidence_actual_amount_nonnegative"),
        ),
        sa.CheckConstraint(
            "length(currency) = 3",
            name=op.f("ck_admin_market_payment_evidence_currency_length"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["admin_market_orders.id"],
            name=op.f(
                "fk_admin_market_payment_evidence_order_id_admin_market_orders"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id", name=op.f("pk_admin_market_payment_evidence")
        ),
        sa.UniqueConstraint(
            "evidence_ref", name=op.f("uq_admin_market_payment_evidence_ref")
        ),
        sa.UniqueConstraint(
            "source_reference_hash",
            name=op.f("uq_admin_market_payment_evidence_source_reference_hash"),
        ),
        sa.UniqueConstraint(
            "submission_idempotency_key_hash",
            name=op.f("uq_admin_market_payment_evidence_submission_idem_hash"),
        ),
    )
    op.create_index(
        op.f("ix_admin_market_payment_evidence_order_status"),
        "admin_market_payment_evidence",
        ["order_id", "status"],
        unique=False,
    )

    op.add_column(
        "admin_market_payment_verifications",
        sa.Column("evidence_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "admin_market_payment_verifications",
        sa.Column("decided_by_user_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "admin_market_payment_verifications",
        sa.Column("decision_reason_code", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "admin_market_payment_verifications",
        sa.Column(
            "decision_idempotency_key_hash", sa.String(length=64), nullable=True
        ),
    )
    op.add_column(
        "admin_market_payment_verifications",
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_admin_market_payment_verification_evidence",
        "admin_market_payment_verifications",
        "admin_market_payment_evidence",
        ["evidence_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_admin_market_payment_verifications_order_id",
        "admin_market_payment_verifications",
        ["order_id"],
    )
    op.create_unique_constraint(
        "uq_admin_market_payment_verifications_decision_idem_hash",
        "admin_market_payment_verifications",
        ["decision_idempotency_key_hash"],
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
    op.drop_constraint(
        op.f("ck_admin_market_audit_records_resource_type_allowed"),
        "admin_market_audit_records",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_admin_market_audit_records_resource_type_allowed"),
        "admin_market_audit_records",
        _AUDIT_RESOURCES,
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM admin_market_payment_evidence)
               OR EXISTS (
                    SELECT 1 FROM admin_market_payment_verifications
                    WHERE evidence_id IS NOT NULL
                       OR decision_idempotency_key_hash IS NOT NULL
               )
               OR EXISTS (
                    SELECT 1 FROM admin_market_audit_records
                    WHERE action = 'payment_evidence_recorded'
                       OR resource_type IN ('contract', 'payment_evidence')
               )
            THEN
                RAISE EXCEPTION
                    'Downgrade blocked: payment evidence or verification exists';
            END IF;
        END $$
        """
    )
    op.drop_constraint(
        op.f("ck_admin_market_audit_records_resource_type_allowed"),
        "admin_market_audit_records",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_admin_market_audit_records_resource_type_allowed"),
        "admin_market_audit_records",
        _PREVIOUS_AUDIT_RESOURCES,
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
    op.drop_constraint(
        "uq_admin_market_payment_verifications_decision_idem_hash",
        "admin_market_payment_verifications",
        type_="unique",
    )
    op.drop_constraint(
        "uq_admin_market_payment_verifications_order_id",
        "admin_market_payment_verifications",
        type_="unique",
    )
    op.drop_constraint(
        "fk_admin_market_payment_verification_evidence",
        "admin_market_payment_verifications",
        type_="foreignkey",
    )
    op.drop_column("admin_market_payment_verifications", "decided_at")
    op.drop_column(
        "admin_market_payment_verifications", "decision_idempotency_key_hash"
    )
    op.drop_column("admin_market_payment_verifications", "decision_reason_code")
    op.drop_column("admin_market_payment_verifications", "decided_by_user_id")
    op.drop_column("admin_market_payment_verifications", "evidence_id")
    op.drop_index(
        op.f("ix_admin_market_payment_evidence_order_status"),
        table_name="admin_market_payment_evidence",
    )
    op.drop_table("admin_market_payment_evidence")
