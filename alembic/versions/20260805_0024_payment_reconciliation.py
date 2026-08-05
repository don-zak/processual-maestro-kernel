"""Add payment reconciliation and exception cases.

Revision ID: 20260805_0024
Revises: 20260805_0023
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260805_0024"
down_revision: str | None = "20260805_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_market_payment_reconciliation_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_ref", sa.String(length=128), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_order_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("exception_type", sa.String(length=32), nullable=False),
        sa.Column("resolution", sa.String(length=32), nullable=True),
        sa.Column("reason_code", sa.String(length=128), nullable=False),
        sa.Column("safe_note", sa.String(length=500), nullable=True),
        sa.Column("decided_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("decision_idempotency_key_hash", sa.String(length=64), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('open', 'requires_review', 'resolved', 'rejected')",
            name=op.f("ck_admin_market_payment_reconciliation_cases_status_allowed"),
        ),
        sa.CheckConstraint(
            "exception_type IN ('underpayment', 'overpayment', 'unknown_reference', "
            "'old_destination', 'late_payment', 'duplicate_payment', 'payer_mismatch', "
            "'currency_mismatch', 'untrusted_evidence', 'other')",
            name=op.f("ck_admin_market_payment_reconciliation_cases_exception_type_allowed"),
        ),
        sa.CheckConstraint(
            "resolution IS NULL OR resolution IN ('accepted_match', 'rejected', "
            "'linked', 'unlinked', 'reevaluated', 'placed_in_review')",
            name=op.f("ck_admin_market_payment_reconciliation_cases_resolution_allowed"),
        ),
        sa.ForeignKeyConstraint(["evidence_id"], ["admin_market_payment_evidence.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["candidate_order_id"], ["admin_market_orders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_ref", name="uq_admin_market_reconciliation_case_ref"),
        sa.UniqueConstraint("evidence_id", name="uq_admin_market_reconciliation_evidence"),
        sa.UniqueConstraint("decision_idempotency_key_hash", name="uq_admin_market_reconciliation_idem_hash"),
    )
    op.create_index(
        "ix_admin_market_reconciliation_status_updated",
        "admin_market_payment_reconciliation_cases",
        ["status", "updated_at"],
    )
    op.drop_constraint(
        op.f("ck_admin_market_audit_records_action_allowed"), "admin_market_audit_records", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_admin_market_audit_records_action_allowed"),
        "admin_market_audit_records",
        "action IN ('authority_checked', 'offer_decided', 'channel_eligibility_decided', "
        "'channel_selected', 'payment_verification_decided', 'subscription_activation_decided', "
        "'payment_destination_created', 'payment_destination_validated', "
        "'payment_destination_activated', 'payment_destination_deactivated', "
        "'payment_destination_default_set', 'order_created', 'contract_completed', "
        "'payment_evidence_recorded', 'payment_reconciliation_decided')",
    )
    op.drop_constraint(
        op.f("ck_admin_market_audit_records_resource_type_allowed"), "admin_market_audit_records", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_admin_market_audit_records_resource_type_allowed"),
        "admin_market_audit_records",
        "resource_type IN ('offer', 'plan', 'order', 'payment_verification', "
        "'subscription', 'trial', 'sales_channel_eligibility', 'payment_destination', "
        "'contract', 'payment_evidence', 'payment_reconciliation')",
    )


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM admin_market_payment_reconciliation_cases) THEN
                RAISE EXCEPTION 'Downgrade blocked: payment reconciliation cases exist';
            END IF;
        END $$
    """)
    op.drop_constraint(
        op.f("ck_admin_market_audit_records_resource_type_allowed"), "admin_market_audit_records", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_admin_market_audit_records_resource_type_allowed"),
        "admin_market_audit_records",
        "resource_type IN ('offer', 'plan', 'order', 'payment_verification', "
        "'subscription', 'trial', 'sales_channel_eligibility', 'payment_destination', "
        "'contract', 'payment_evidence')",
    )
    op.drop_constraint(
        op.f("ck_admin_market_audit_records_action_allowed"), "admin_market_audit_records", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_admin_market_audit_records_action_allowed"),
        "admin_market_audit_records",
        "action IN ('authority_checked', 'offer_decided', 'channel_eligibility_decided', "
        "'channel_selected', 'payment_verification_decided', 'subscription_activation_decided', "
        "'payment_destination_created', 'payment_destination_validated', "
        "'payment_destination_activated', 'payment_destination_deactivated', "
        "'payment_destination_default_set', 'order_created', 'contract_completed', "
        "'payment_evidence_recorded')",
    )
    op.drop_index(
        "ix_admin_market_reconciliation_status_updated", table_name="admin_market_payment_reconciliation_cases"
    )
    op.drop_table("admin_market_payment_reconciliation_cases")
