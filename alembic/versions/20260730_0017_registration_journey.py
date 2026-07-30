"""add persistent registration journey

Revision ID: 20260730_0017
Revises: 20260730_0016
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260730_0017"
down_revision: str | None = "20260730_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "registration_intents",
        sa.Column("intent_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("plan_slug", sa.String(length=128), nullable=False),
        sa.Column("catalog_version", sa.String(length=128), nullable=False),
        sa.Column("source_context", sa.String(length=64), nullable=False),
        sa.Column("billing_cycle", sa.String(length=16), nullable=True),
        sa.Column("account_type", sa.String(length=24), nullable=True),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("session_binding_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("intent_id", name="pk_registration_intents"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name="fk_registration_intents_user_id_identity_users",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "session_binding_hash",
            "plan_id",
            name="uq_registration_intent_session_plan",
        ),
        sa.CheckConstraint("version >= 0", name=op.f("ck_registration_intents_version_nonnegative")),
        sa.CheckConstraint(
            "state IN ('plan_selected','registration_pending','email_verification_pending','profile_pending')",
            name=op.f("ck_registration_intents_state_allowed"),
        ),
    )
    op.create_index(
        "ix_registration_intents_expiry_state",
        "registration_intents",
        ["expires_at", "state"],
        unique=False,
    )
    op.create_table(
        "registration_journey_checkpoints",
        sa.Column("checkpoint_id", sa.Uuid(), nullable=False),
        sa.Column("intent_id", sa.Uuid(), nullable=False),
        sa.Column("current_step", sa.String(length=32), nullable=False),
        sa.Column("recovery_action", sa.String(length=128), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("last_valid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("checkpoint_id", name="pk_registration_journey_checkpoints"),
        sa.ForeignKeyConstraint(
            ["intent_id"],
            ["registration_intents.intent_id"],
            name="fk_registration_checkpoint_intent",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("intent_id", name="uq_registration_journey_checkpoint_intent"),
        sa.CheckConstraint(
            "state_version >= 0",
            name=op.f("ck_registration_journey_checkpoints_state_version_nonnegative"),
        ),
    )


def downgrade() -> None:
    op.drop_table("registration_journey_checkpoints")
    op.drop_index("ix_registration_intents_expiry_state", table_name="registration_intents")
    op.drop_table("registration_intents")
