"""Persist bounded administrator onboarding MFA proof.

Revision ID: 20260818_0050
Revises: 20260818_0049
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa

revision = "20260818_0050"
down_revision = "20260818_0049"
branch_labels = None
depends_on = None

PROOF_INDEX = "uq_admin_governance_invitations_onboarding_mfa_proof_hash"


def upgrade() -> None:
    op.add_column(
        "admin_governance_invitations",
        sa.Column("onboarding_mfa_proof_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "admin_governance_invitations",
        sa.Column(
            "onboarding_mfa_proof_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        PROOF_INDEX,
        "admin_governance_invitations",
        ["onboarding_mfa_proof_hash"],
        unique=True,
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        row = bind.execute(
            sa.text(
                "SELECT id FROM admin_governance_invitations "
                "WHERE onboarding_mfa_proof_hash IS NOT NULL LIMIT 1"
            )
        ).first()
        if row is not None:
            raise RuntimeError(
                "Downgrade blocked: administrator onboarding MFA proofs exist"
            )

    op.drop_index(PROOF_INDEX, table_name="admin_governance_invitations")
    op.drop_column(
        "admin_governance_invitations",
        "onboarding_mfa_proof_expires_at",
    )
    op.drop_column(
        "admin_governance_invitations",
        "onboarding_mfa_proof_hash",
    )
