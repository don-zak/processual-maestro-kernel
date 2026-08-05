"""Generalize authentication delivery authority for account recovery.

Revision ID: 20260723_0010
Revises: 20260723_0009
"""

import sqlalchemy as sa

from alembic import op

revision = "20260723_0010"
down_revision = "20260723_0009"
branch_labels = None
depends_on = None

DELIVERY_EVENT_CONSTRAINT = "ck_auth_delivery_outbox_event_type_allowed"
DELIVERY_AUTHORITY_CONSTRAINT = "ck_auth_delivery_outbox_exactly_one_authority"
RECOVERY_REQUEST_FK = "fk_auth_delivery_outbox_account_recovery_request"
RECOVERY_REQUEST_UQ = "uq_auth_delivery_outbox_account_recovery_request_id"


def upgrade() -> None:
    with op.batch_alter_table("auth_delivery_outbox") as batch_op:
        batch_op.add_column(
            sa.Column(
                "account_recovery_request_id",
                sa.Uuid(),
                nullable=True,
            )
        )
        batch_op.alter_column(
            "action_token_id",
            existing_type=sa.Uuid(),
            nullable=True,
        )
        batch_op.create_foreign_key(
            RECOVERY_REQUEST_FK,
            "auth_account_recovery_requests",
            ["account_recovery_request_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_unique_constraint(
            RECOVERY_REQUEST_UQ,
            ["account_recovery_request_id"],
        )
        batch_op.create_check_constraint(
            DELIVERY_AUTHORITY_CONSTRAINT,
            """
            (
                action_token_id IS NOT NULL
                AND account_recovery_request_id IS NULL
            )
            OR
            (
                action_token_id IS NULL
                AND account_recovery_request_id IS NOT NULL
            )
            """,
        )
        batch_op.drop_constraint(
            DELIVERY_EVENT_CONSTRAINT,
            type_="check",
        )
        batch_op.create_check_constraint(
            DELIVERY_EVENT_CONSTRAINT,
            """
            event_type IN (
                'verify_email',
                'verify_recovery_email',
                'account_recovery_verification'
            )
            """,
        )


def downgrade() -> None:
    with op.batch_alter_table("auth_delivery_outbox") as batch_op:
        batch_op.drop_constraint(
            DELIVERY_EVENT_CONSTRAINT,
            type_="check",
        )
        batch_op.create_check_constraint(
            DELIVERY_EVENT_CONSTRAINT,
            """
            event_type IN (
                'verify_email',
                'verify_recovery_email'
            )
            """,
        )
        batch_op.drop_constraint(
            DELIVERY_AUTHORITY_CONSTRAINT,
            type_="check",
        )
        batch_op.drop_constraint(
            RECOVERY_REQUEST_UQ,
            type_="unique",
        )
        batch_op.drop_constraint(
            RECOVERY_REQUEST_FK,
            type_="foreignkey",
        )
        batch_op.alter_column(
            "action_token_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )
        batch_op.drop_column("account_recovery_request_id")
