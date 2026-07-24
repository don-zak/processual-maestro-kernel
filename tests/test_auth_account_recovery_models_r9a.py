from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlalchemy.exc import StatementError

from processual_api.auth.models import (
    IDENTITY_AUTH_MODELS,
    AuthAccountRecoveryRequest,
    IdentityUser,
)

NOW = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)


def test_account_recovery_model_is_exported_without_mutating_r2_catalog() -> None:
    import processual_api.auth.models as auth_models

    assert AuthAccountRecoveryRequest not in IDENTITY_AUTH_MODELS
    assert "AuthAccountRecoveryRequest" in auth_models.__all__
    assert AuthAccountRecoveryRequest.__tablename__ == "auth_account_recovery_requests"
    assert "auth_account_recovery_requests" in AuthAccountRecoveryRequest.metadata.tables


def test_identity_user_exposes_recovery_request_relationship() -> None:
    assert "account_recovery_requests" in IdentityUser.__mapper__.relationships
    relationship = IdentityUser.__mapper__.relationships["account_recovery_requests"]
    assert relationship.mapper.class_ is AuthAccountRecoveryRequest
    assert "delete-orphan" in relationship.cascade


def test_account_recovery_columns_are_exact() -> None:
    columns = AuthAccountRecoveryRequest.__table__.columns

    assert set(columns.keys()) == {
        "id",
        "user_id",
        "recovery_email_id",
        "purpose",
        "state",
        "verification_token_hash",
        "completion_token_hash",
        "attempt_count",
        "expires_at",
        "verified_at",
        "completed_at",
        "revoked_at",
        "created_at",
        "updated_at",
    }

    assert columns["verification_token_hash"].nullable is False
    assert columns["completion_token_hash"].nullable is True
    assert columns["expires_at"].nullable is False
    assert columns["attempt_count"].nullable is False


def test_account_recovery_model_contains_no_raw_secret_columns() -> None:
    column_names = {column.name.lower() for column in AuthAccountRecoveryRequest.__table__.columns}

    forbidden = {
        "token",
        "verification_token",
        "completion_token",
        "password",
        "new_password",
        "confirm_password",
        "raw_token",
        "raw_secret",
        "secret",
        "api_key",
        "refresh_token",
        "access_token",
    }

    assert column_names.isdisjoint(forbidden)
    assert "verification_token_hash" in column_names
    assert "completion_token_hash" in column_names


def test_account_recovery_constraints_are_present() -> None:
    constraints = AuthAccountRecoveryRequest.__table__.constraints

    check_sql = {str(constraint.sqltext) for constraint in constraints if isinstance(constraint, CheckConstraint)}
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert any("platform_account_recovery" in expression for expression in check_sql)
    assert any(
        "pending" in expression
        and "verified" in expression
        and "completed" in expression
        and "expired" in expression
        and "revoked" in expression
        for expression in check_sql
    )
    assert any("attempt_count >= 0" in expression for expression in check_sql)

    assert ("verification_token_hash",) in unique_columns
    assert ("completion_token_hash",) in unique_columns


def test_account_recovery_indexes_are_exact() -> None:
    indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in AuthAccountRecoveryRequest.__table__.indexes
        if isinstance(index, Index)
    }

    assert indexes == {
        "ix_auth_account_recovery_expiry": (
            "state",
            "expires_at",
        ),
        "ix_auth_account_recovery_user_state": (
            "user_id",
            "state",
            "expires_at",
        ),
    }


def test_account_recovery_foreign_key_delete_policies() -> None:
    foreign_keys = {
        foreign_key.parent.name: (
            foreign_key.target_fullname,
            foreign_key.ondelete,
        )
        for foreign_key in AuthAccountRecoveryRequest.__table__.foreign_keys
    }

    assert foreign_keys == {
        "user_id": (
            "identity_users.id",
            "CASCADE",
        ),
        "recovery_email_id": (
            "identity_user_email_addresses.id",
            "SET NULL",
        ),
    }


def test_model_defaults_are_fail_safe() -> None:
    purpose_default = AuthAccountRecoveryRequest.__table__.columns["purpose"].default
    state_default = AuthAccountRecoveryRequest.__table__.columns["state"].default
    attempt_default = AuthAccountRecoveryRequest.__table__.columns["attempt_count"].default

    assert purpose_default is not None
    assert purpose_default.arg == "platform_account_recovery"
    assert state_default is not None
    assert state_default.arg == "pending"
    assert attempt_default is not None
    assert attempt_default.arg == 0


def test_model_accepts_hash_only_recovery_state() -> None:
    request = AuthAccountRecoveryRequest(
        id=uuid4(),
        user_id=uuid4(),
        recovery_email_id=uuid4(),
        purpose="platform_account_recovery",
        state="pending",
        verification_token_hash="a" * 64,
        completion_token_hash=None,
        attempt_count=0,
        expires_at=NOW,
    )

    assert request.verification_token_hash == "a" * 64
    assert request.completion_token_hash is None
    assert request.state == "pending"


def test_uuid_columns_reject_plain_invalid_values_during_binding() -> None:
    column = AuthAccountRecoveryRequest.__table__.columns["user_id"]

    with pytest.raises((StatementError, AttributeError, TypeError, ValueError)):
        column.type.bind_processor(None)("not-a-uuid")
