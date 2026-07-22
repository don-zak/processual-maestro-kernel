from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import CheckConstraint, UniqueConstraint

from processual_api.auth.models import (
    IdentityPlatformAuthority,
    IdentityUser,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT
    / "alembic"
    / "versions"
    / "20260722_0006_platform_authority.py"
)


def _load_migration():
    specification = importlib.util.spec_from_file_location(
        "auth_r8d_platform_authority_migration",
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
        for constraint in IdentityPlatformAuthority.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }


def test_platform_authority_is_independent_from_organization_membership() -> None:
    table = IdentityPlatformAuthority.__table__

    assert table.name == "identity_platform_authorities"
    assert "organization_id" not in table.columns
    assert "user_id" in table.columns
    assert "authority" in table.columns
    assert "status" in table.columns


def test_platform_authority_allows_only_governed_platform_admin() -> None:
    constraints = _check_constraint_texts()

    assert "authority IN ('platform_admin')" in constraints
    assert "status IN ('active', 'revoked')" in constraints


def test_platform_authority_constraint_names_remain_identifiable() -> None:
    constraint_names = {
        constraint.name or ""
        for constraint in IdentityPlatformAuthority.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert any(
        name == "authority_allowed"
        or name.endswith("_authority_allowed")
        for name in constraint_names
    )
    assert any(
        name == "status_allowed"
        or name.endswith("_status_allowed")
        for name in constraint_names
    )


def test_platform_authority_is_unique_per_user_and_authority() -> None:
    unique_constraints = [
        constraint
        for constraint in IdentityPlatformAuthority.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    matching = [
        constraint
        for constraint in unique_constraints
        if constraint.name
        == "uq_identity_platform_authority_user_authority"
    ]

    assert len(matching) == 1
    assert [
        column.name
        for column in matching[0].columns
    ] == ["user_id", "authority"]


def test_identity_user_owns_platform_authority_relationship() -> None:
    relationship = IdentityUser.platform_authorities.property

    assert relationship.mapper.class_ is IdentityPlatformAuthority
    assert relationship.back_populates == "user"
    assert "delete-orphan" in relationship.cascade


def test_platform_authority_records_governed_grant_and_revocation() -> None:
    columns = IdentityPlatformAuthority.__table__.columns

    required = {
        "granted_by_user_id",
        "grant_reason",
        "granted_at",
        "revoked_by_user_id",
        "revoke_reason",
        "revoked_at",
    }

    assert required.issubset(columns.keys())
    assert columns["grant_reason"].nullable is False
    assert columns["revoked_at"].nullable is True


def test_platform_authority_migration_extends_current_head() -> None:
    migration = _load_migration()

    assert migration.revision == "20260722_0006"
    assert migration.down_revision == "20260722_0005"
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)
