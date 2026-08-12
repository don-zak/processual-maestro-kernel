from dataclasses import replace

import pytest
from pydantic import ValidationError

from processual_api.auth.registration_contracts import (
    IdentityRegistrationSecurityContract,
    IndividualRegistrationRequestContract,
    RegistrationMode,
    get_identity_registration_security_contract,
)


def _individual_request(**overrides):
    payload = {
        "email": "user@example.com",
        "full_name": "Example User",
        "password": "a sufficiently long password",
        "accepted_terms_version": "2026-01",
    }
    payload.update(overrides)
    return IndividualRegistrationRequestContract(**payload)


def test_plan_and_billing_must_be_supplied_as_a_valid_pair() -> None:
    with pytest.raises(ValidationError, match="must be provided together"):
        _individual_request(selected_plan_id="pro")

    with pytest.raises(ValidationError, match="must be provided together"):
        _individual_request(billing_period="monthly")

    with pytest.raises(ValidationError, match="must be monthly or annual"):
        _individual_request(selected_plan_id="pro", billing_period="weekly")

    monthly = _individual_request(selected_plan_id="pro", billing_period="monthly")
    annual = _individual_request(selected_plan_id="pro", billing_period="annual")

    assert monthly.selected_plan_id == "pro"
    assert monthly.billing_period == "monthly"
    assert annual.billing_period == "annual"


@pytest.mark.parametrize(
    ("field_name", "unsafe_value", "message"),
    (
        ("contract_id", "   ", "contract_id must not be empty"),
        ("password_hash_algorithm", "bcrypt", "must use Argon2id"),
        ("access_token_storage", "local_storage", "must remain memory-only"),
        ("refresh_token_storage", "memory", "must use an HttpOnly cookie"),
        ("session_source_of_truth", "redis", "PostgreSQL must remain"),
        ("rate_limit_store", "postgresql", "Redis is required only"),
        ("mfa_primary_method", "sms", "initial second factor must be TOTP"),
    ),
)
def test_contract_rejects_weakened_architecture_values(
    field_name: str,
    unsafe_value: str,
    message: str,
) -> None:
    contract = get_identity_registration_security_contract()

    with pytest.raises(ValueError, match=message):
        replace(contract, **{field_name: unsafe_value})


@pytest.mark.parametrize(
    "field_name",
    (
        "privileged_mfa_required",
        "mfa_secret_encrypted",
        "mfa_recovery_codes_hashed",
        "mfa_replay_protection_required",
    ),
)
def test_contract_rejects_remaining_required_true_flags(field_name: str) -> None:
    contract = get_identity_registration_security_contract()

    with pytest.raises(ValueError, match=f"{field_name} must remain enabled"):
        replace(contract, **{field_name: False})


@pytest.mark.parametrize(
    "field_name",
    (
        "raw_mfa_secret_persisted",
        "raw_recovery_code_persisted",
        "sms_authentication_factor_allowed",
    ),
)
def test_contract_rejects_remaining_required_false_flags(field_name: str) -> None:
    contract = get_identity_registration_security_contract()

    with pytest.raises(ValueError, match=f"{field_name} must remain disabled"):
        replace(contract, **{field_name: True})


def test_platform_admin_bootstrap_cannot_be_public_self_service() -> None:
    with pytest.raises(ValueError, match="cannot be public self-service"):
        IdentityRegistrationSecurityContract(
            public_self_service_modes=(RegistrationMode.PLATFORM_ADMIN_BOOTSTRAP,),
        )
