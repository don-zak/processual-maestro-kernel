from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect

from processual_api.auth.models import (
    IDENTITY_AUTH_MODELS,
    AuthMfaChallenge,
    AuthMfaFactor,
    AuthMfaRecoveryCode,
    AuthRefreshToken,
    AuthSession,
    IdentityOrganization,
    IdentityUser,
    OrganizationMembership,
)
from processual_api.auth.registration_contracts import (
    IdentityRegistrationSecurityContract,
    get_identity_registration_security_contract,
)
from processual_api.db.base import Base

EXPECTED_TABLES = {
    "identity_users",
    "identity_organizations",
    "identity_memberships",
    "identity_terms_acceptances",
    "auth_sessions",
    "auth_refresh_tokens",
    "auth_action_tokens",
    "auth_mfa_factors",
    "auth_mfa_recovery_codes",
    "auth_mfa_challenges",
}


def _column_names(model: type[Base]) -> set[str]:
    return {column.name for column in model.__table__.columns}


def test_identity_auth_metadata_has_the_exact_r2_table_catalog() -> None:
    assert len(IDENTITY_AUTH_MODELS) == 10
    assert {model.__tablename__ for model in IDENTITY_AUTH_MODELS} == EXPECTED_TABLES
    assert EXPECTED_TABLES.issubset(Base.metadata.tables)


def test_identity_and_tenant_authority_are_separate() -> None:
    assert "email_normalized" in _column_names(IdentityUser)
    assert "password_hash" in _column_names(IdentityUser)
    assert "slug_normalized" in _column_names(IdentityOrganization)
    assert "role" not in _column_names(IdentityUser)
    assert "plan_id" not in _column_names(IdentityUser)
    assert "role" in _column_names(OrganizationMembership)

    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in OrganizationMembership.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("user_id", "organization_id") in unique_columns


def test_session_and_refresh_rotation_state_support_reuse_detection() -> None:
    assert {
        "refresh_family_id",
        "mfa_satisfied_at",
        "expires_at",
        "revoked_at",
    }.issubset(_column_names(AuthSession))
    assert {
        "token_hash",
        "parent_token_id",
        "consumed_at",
        "revoked_at",
        "reuse_detected_at",
    }.issubset(_column_names(AuthRefreshToken))
    assert "refresh_token" not in _column_names(AuthRefreshToken)


def test_totp_factor_is_encrypted_and_recovery_material_is_hash_only() -> None:
    factor_columns = _column_names(AuthMfaFactor)
    recovery_columns = _column_names(AuthMfaRecoveryCode)
    challenge_columns = _column_names(AuthMfaChallenge)

    assert {
        "factor_type",
        "secret_ciphertext",
        "secret_key_version",
        "last_used_step",
    }.issubset(factor_columns)
    assert "secret" not in factor_columns
    assert "code_hash" in recovery_columns
    assert "code" not in recovery_columns
    assert "challenge_hash" in challenge_columns
    assert "challenge" not in challenge_columns
    assert "attempt_count" in challenge_columns


def test_security_contract_requires_totp_for_privileged_access() -> None:
    contract = get_identity_registration_security_contract()

    assert contract.mfa_primary_method == "totp"
    assert contract.privileged_mfa_required is True
    assert contract.mfa_secret_encrypted is True
    assert contract.mfa_recovery_codes_hashed is True
    assert contract.mfa_replay_protection_required is True
    assert contract.sms_authentication_factor_allowed is False
    assert contract.raw_mfa_secret_persisted is False
    assert contract.raw_recovery_code_persisted is False


def test_security_contract_rejects_weakened_mfa_policy() -> None:
    with pytest.raises(ValueError):
        IdentityRegistrationSecurityContract(privileged_mfa_required=False)
    with pytest.raises(ValueError):
        IdentityRegistrationSecurityContract(mfa_secret_encrypted=False)
    with pytest.raises(ValueError):
        IdentityRegistrationSecurityContract(mfa_recovery_codes_hashed=False)
    with pytest.raises(ValueError):
        IdentityRegistrationSecurityContract(mfa_replay_protection_required=False)
    with pytest.raises(ValueError):
        IdentityRegistrationSecurityContract(sms_authentication_factor_allowed=True)
    with pytest.raises(ValueError):
        IdentityRegistrationSecurityContract(raw_mfa_secret_persisted=True)
    with pytest.raises(ValueError):
        IdentityRegistrationSecurityContract(raw_recovery_code_persisted=True)


def test_sensitive_persistence_columns_are_hashes_or_ciphertext() -> None:
    forbidden_raw_names = {
        "password",
        "token",
        "refresh_token",
        "action_token",
        "secret",
        "recovery_code",
        "challenge",
    }
    all_columns = {column.name for model in IDENTITY_AUTH_MODELS for column in model.__table__.columns}
    assert all_columns.isdisjoint(forbidden_raw_names)
    assert "password_hash" in all_columns
    assert "token_hash" in all_columns
    assert "secret_ciphertext" in all_columns
    assert "code_hash" in all_columns
    assert "challenge_hash" in all_columns


def test_r2_metadata_can_create_and_drop_with_foreign_keys_enabled() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(connection)
        assert EXPECTED_TABLES.issubset(inspect(connection).get_table_names())
        Base.metadata.drop_all(connection)
        assert EXPECTED_TABLES.isdisjoint(inspect(connection).get_table_names())
