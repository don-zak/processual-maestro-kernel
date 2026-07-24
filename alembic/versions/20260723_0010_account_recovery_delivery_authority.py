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

DELIVERY_EVENT_CONSTRAINT = "ck_auth_delivery_outbox_ck_auth_delivery_outbox_event_t_8c12"

DELIVERY_AUTHORITY_CONSTRAINT = "ck_auth_delivery_outbox_exactly_one_authority"

RECOVERY_REQUEST_FK = "fk_auth_delivery_outbox_account_recovery_request"

RECOVERY_REQUEST_UQ = "uq_auth_delivery_outbox_account_recovery_request_id"


def upgrade() -> None:
    op.add_column(
        "auth_delivery_outbox",
        sa.Column(
            "account_recovery_request_id",
            sa.Uuid(),
            nullable=True,
        ),
    )

    op.alter_column(
        "auth_delivery_outbox",
        "action_token_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )

    op.create_foreign_key(
        RECOVERY_REQUEST_FK,
        "auth_delivery_outbox",
        "auth_account_recovery_requests",
        ["account_recovery_request_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_unique_constraint(
        RECOVERY_REQUEST_UQ,
        "auth_delivery_outbox",
        ["account_recovery_request_id"],
    )

    op.create_check_constraint(
        DELIVERY_AUTHORITY_CONSTRAINT,
        "auth_delivery_outbox",
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

    op.execute(
        f"""
        ALTER TABLE auth_delivery_outbox
        DROP CONSTRAINT {DELIVERY_EVENT_CONSTRAINT}
        """
    )

    op.execute(
        f"""
        ALTER TABLE auth_delivery_outbox
        ADD CONSTRAINT {DELIVERY_EVENT_CONSTRAINT}
        CHECK (
            event_type IN (
                'verify_email',
                'verify_recovery_email',
                'account_recovery_verification'
            )
        )
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE auth_delivery_outbox
        DROP CONSTRAINT {DELIVERY_EVENT_CONSTRAINT}
        """
    )

    op.execute(
        f"""
        ALTER TABLE auth_delivery_outbox
        ADD CONSTRAINT {DELIVERY_EVENT_CONSTRAINT}
        CHECK (
            event_type IN (
                'verify_email',
                'verify_recovery_email'
            )
        )
        """
    )

    op.drop_constraint(
        DELIVERY_AUTHORITY_CONSTRAINT,
        "auth_delivery_outbox",
        type_="check",
    )

    op.drop_constraint(
        RECOVERY_REQUEST_UQ,
        "auth_delivery_outbox",
        type_="unique",
    )

    op.drop_constraint(
        RECOVERY_REQUEST_FK,
        "auth_delivery_outbox",
        type_="foreignkey",
    )

    op.alter_column(
        "auth_delivery_outbox",
        "action_token_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )

    op.drop_column(
        "auth_delivery_outbox",
        "account_recovery_request_id",
    )
