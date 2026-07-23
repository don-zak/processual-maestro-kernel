from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import CheckConstraint, UniqueConstraint

from processual_api.auth.models import IdentityUser, IdentityUserEmailAddress

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "alembic" / "versions" / "20260723_0007_admin_recovery_email_supervisor_authority.py"


def _load_migration():
    specification = importlib.util.spec_from_file_location(
        "auth_r8d_admin_recovery_email_migration",
        MIGRATION_PATH,
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _check_constraint_texts() -> set[str]:
    return {
        " ".join(str(constraint.sqltext).split())
        for constraint in IdentityUserEmailAddress.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }


def test_recovery_email_is_separate_from_primary_login_email() -> None:
    table = IdentityUserEmailAddress.__table__
    assert table.name == "identity_user_email_addresses"
    assert "email_normalized" in table.columns
    assert "purpose" in table.columns
    assert "status" in table.columns
    assert "verified_at" in table.columns
    assert "revoked_at" in table.columns
    assert "password_hash" not in table.columns


def test_recovery_email_allows_only_governed_lifecycle() -> None:
    constraints = _check_constraint_texts()
    assert "purpose IN ('recovery')" in constraints
    assert "status IN ('pending', 'verified', 'revoked')" in constraints


def test_recovery_email_is_unique_globally_and_per_user_purpose() -> None:
    unique_column_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in IdentityUserEmailAddress.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("email_normalized",) in unique_column_sets
    assert ("user_id", "purpose") in unique_column_sets


def test_identity_user_owns_recovery_email_relationship() -> None:
    relationship = IdentityUser.email_addresses.property
    assert relationship.mapper.class_ is IdentityUserEmailAddress
    assert relationship.back_populates == "user"
    assert "delete-orphan" in relationship.cascade


def test_recovery_email_migration_extends_current_head() -> None:
    migration = _load_migration()
    assert migration.revision == "20260723_0007"
    assert migration.down_revision == "20260722_0006"


def test_recovery_email_migration_has_upgrade_and_downgrade() -> None:
    migration = _load_migration()
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)
