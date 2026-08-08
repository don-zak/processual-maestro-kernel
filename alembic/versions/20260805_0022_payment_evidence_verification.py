"""Add safe payment evidence matching and administrator verification.

Revision ID: 20260805_0022
Revises: 20260805_0021
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "20260805_0022"
down_revision: str | None = "20260805_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VERIFICATION_TABLE = "admin_market_payment_verifications"
AUDIT_TABLE = "admin_market_audit_records"

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


def _reflected_check_names() -> set[str]:
    action_name = op.f("ck_admin_market_audit_records_action_allowed")
    resource_name = op.f("ck_admin_market_audit_records_resource_type_allowed")
    if context.is_offline_mode():
        return {action_name, resource_name}
    inspector = sa.inspect(op.get_bind())
    return {
        constraint["name"]
        for constraint in inspector.get_check_constraints(AUDIT_TABLE)
        if constraint.get("name")
    }


def _replace_audit_constraints(action_check: str, resource_check: str) -> None:
    action_name = op.f("ck_admin_market_audit_records_action_allowed")
    resource_name = op.f("ck_admin_market_audit_records_resource_type_allowed")
    reflected = _reflected_check_names()
    with op.batch_alter_table(AUDIT_TABLE) as batch_op:
        if action_name in reflected:
            batch_op.drop_constraint(action_name, type_="check")
        if resource_name in reflected:
            batch_op.drop_constraint(resource_name, type_="check")
        batch_op.create_check_constraint(action_name, action_check)
        batch_op.create_check_constraint(resource_name, resource_check)


def _assert_safe_to_downgrade() -> None:
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    checks = (
        sa.text("SELECT 1 FROM admin_market_payment_evidence LIMIT 1"),
        sa.text(
            "SELECT 1 FROM admin_market_payment_verifications "
            "WHERE evidence_id IS NOT NULL "
            "OR decision_idempotency_key_hash IS NOT NULL LIMIT 1"
        ),
        sa.text(
            "SELECT 1 FROM admin_market_audit_records "
            "WHERE action = 'payment_evidence_recorded' "
            "OR resource_type IN ('contract', 'payment_evidence') LIMIT 1"
        ),
    )
    if any(connection.execute(query).first() for query in checks):
        raise RuntimeError(
            "Downgrade blocked: payment evidence or verification exists"
        )


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
        sa.Column("submission_idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("reference_matched", sa.Boolean(), nullable=False),
        sa.Column("amount_matched", sa.Boolean(), nullable=False),
        sa.Column("currency_matched", sa.Boolean(), nullable=False),
        sa.Column("destination_matched", sa.Boolean(), nullable=False),
        sa.Column("match_reason_code", sa.String(length=128), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
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
            ["order_id"], ["admin_market_orders.id"],
            name=op.f("fk_admin_market_payment_evidence_order_id_admin_market_orders"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_market_payment_evidence")),
        sa.UniqueConstraint("evidence_ref", name=op.f("uq_admin_market_payment_evidence_ref")),
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

    with op.batch_alter_table(VERIFICATION_TABLE) as batch_op:
        batch_op.add_column(sa.Column("evidence_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("decided_by_user_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("decision_reason_code", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("decision_idempotency_key_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key(
            "fk_admin_market_payment_verification_evidence",
            "admin_market_payment_evidence",
            ["evidence_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_unique_constraint(
            "uq_admin_market_payment_verifications_order_id",
            ["order_id"],
        )
        batch_op.create_unique_constraint(
            "uq_admin_market_payment_verifications_decision_idem_hash",
            ["decision_idempotency_key_hash"],
        )

    _replace_audit_constraints(_AUDIT_ACTIONS, _AUDIT_RESOURCES)


def downgrade() -> None:
    _assert_safe_to_downgrade()
    _replace_audit_constraints(_PREVIOUS_AUDIT_ACTIONS, _PREVIOUS_AUDIT_RESOURCES)

    with op.batch_alter_table(VERIFICATION_TABLE) as batch_op:
        batch_op.drop_constraint(
            "uq_admin_market_payment_verifications_decision_idem_hash",
            type_="unique",
        )
        batch_op.drop_constraint(
            "uq_admin_market_payment_verifications_order_id",
            type_="unique",
        )
        batch_op.drop_constraint(
            "fk_admin_market_payment_verification_evidence",
            type_="foreignkey",
        )
        batch_op.drop_column("decided_at")
        batch_op.drop_column("decision_idempotency_key_hash")
        batch_op.drop_column("decision_reason_code")
        batch_op.drop_column("decided_by_user_id")
        batch_op.drop_column("evidence_id")

    op.drop_index(
        op.f("ix_admin_market_payment_evidence_order_status"),
        table_name="admin_market_payment_evidence",
    )
    op.drop_table("admin_market_payment_evidence")
