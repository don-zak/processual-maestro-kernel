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


def _replace_check_constraint(
    *,
    table_name: str,
    constraint_name: str,
    expression: str,
) -> None:
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.drop_constraint(constraint_name, type_="check")
        batch_op.create_check_constraint(constraint_name, expression)


def upgrade() -> None:
    _replace_check_constraint(
        table_name="auth_action_tokens",
        constraint_name=ACTION_CONSTRAINT,
        expression=(
            "purpose IN ('verify_email', 'verify_recovery_email', "
            "'reset_password', 'change_email', 'accept_invitation')"
        ),
    )
    _replace_check_constraint(
        table_name="auth_delivery_outbox",
        constraint_name=DELIVERY_CONSTRAINT,
        expression="event_type IN ('verify_email', 'verify_recovery_email')",
    )


def downgrade() -> None:
    _replace_check_constraint(
        table_name="auth_delivery_outbox",
        constraint_name=DELIVERY_CONSTRAINT,
        expression="event_type IN ('verify_email')",
    )
    _replace_check_constraint(
        table_name="auth_action_tokens",
        constraint_name=ACTION_CONSTRAINT,
        expression=(
            "purpose IN ('verify_email', 'reset_password', "
            "'change_email', 'accept_invitation')"
        ),
    )
