"""Add recovery email verification token lifecycle.

Revision ID: 20260723_0008
Revises: 20260723_0007
"""

from alembic import op

revision = "20260723_0008"
down_revision = "20260723_0007"
branch_labels = None
depends_on = None

ACTION_CONSTRAINT = (
    "ck_auth_action_tokens_"
    "ck_auth_action_tokens_purpose_allowed"
)
DELIVERY_CONSTRAINT = (
    "ck_auth_delivery_outbox_"
    "ck_auth_delivery_outbox_event_t_8c12"
)


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE auth_action_tokens
        DROP CONSTRAINT {ACTION_CONSTRAINT}
        """
    )
    op.execute(
        f"""
        ALTER TABLE auth_action_tokens
        ADD CONSTRAINT {ACTION_CONSTRAINT}
        CHECK (
            purpose IN (
                'verify_email',
                'verify_recovery_email',
                'reset_password',
                'change_email',
                'accept_invitation'
            )
        )
        """
    )

    op.execute(
        f"""
        ALTER TABLE auth_delivery_outbox
        DROP CONSTRAINT {DELIVERY_CONSTRAINT}
        """
    )
    op.execute(
        f"""
        ALTER TABLE auth_delivery_outbox
        ADD CONSTRAINT {DELIVERY_CONSTRAINT}
        CHECK (
            event_type IN (
                'verify_email',
                'verify_recovery_email'
            )
        )
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE auth_delivery_outbox
        DROP CONSTRAINT {DELIVERY_CONSTRAINT}
        """
    )
    op.execute(
        f"""
        ALTER TABLE auth_delivery_outbox
        ADD CONSTRAINT {DELIVERY_CONSTRAINT}
        CHECK (event_type IN ('verify_email'))
        """
    )

    op.execute(
        f"""
        ALTER TABLE auth_action_tokens
        DROP CONSTRAINT {ACTION_CONSTRAINT}
        """
    )
    op.execute(
        f"""
        ALTER TABLE auth_action_tokens
        ADD CONSTRAINT {ACTION_CONSTRAINT}
        CHECK (
            purpose IN (
                'verify_email',
                'reset_password',
                'change_email',
                'accept_invitation'
            )
        )
        """
    )
