from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from processual_api.auth.registration_contracts import (
    AccountStatus,
    AuthActionPurpose,
    IdentityRegistrationSecurityContract,
    IndividualRegistrationRequestContract,
    LoginRequestContract,
    MembershipRole,
    OrganizationRegistrationRequestContract,
    RegistrationAcceptedResponseContract,
    RegistrationMode,
    get_identity_registration_security_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def test_registration_modes_are_hybrid_and_platform_admin_is_not_public() -> None:
    contract = get_identity_registration_security_contract()

    assert contract.public_self_service_modes == (
        RegistrationMode.INDIVIDUAL,
        RegistrationMode.ORGANIZATION,
    )
    assert contract.review_required_modes == (
        RegistrationMode.ENTERPRISE_APPLICATION,
    )
    assert (
        RegistrationMode.PLATFORM_ADMIN_BOOTSTRAP
        not in contract.public_self_service_modes
    )
    assert contract.platform_admin_public_registration is False


def test_registration_and_login_requests_forbid_authority_fields() -> None:
    with pytest.raises(ValidationError):
        IndividualRegistrationRequestContract(
            email="user@example.com",
            full_name="Example User",
            password="a sufficiently long password",
            accepted_terms_version="2026-01",
            role="platform_admin",
        )

    with pytest.raises(ValidationError):
        OrganizationRegistrationRequestContract(
            email="owner@example.com",
            full_name="Example Owner",
            password="another sufficiently long password",
            accepted_terms_version="2026-01",
            organization_name="Example Organization",
            plan_id="enterprise",
        )

    with pytest.raises(ValidationError):
        LoginRequestContract(
            email="user@example.com",
            password="password",
            role="admin",
        )


def test_registration_safe_response_does_not_expose_identity_or_tokens() -> None:
    payload = RegistrationAcceptedResponseContract().model_dump()

    assert payload == {
        "status": "accepted",
        "next_action": "check_email",
    }
    assert not {
        "user_id",
        "organization_id",
        "email_exists",
        "access_token",
        "refresh_token",
    }.intersection(payload)


def test_roles_and_tenant_context_are_server_derived() -> None:
    contract = get_identity_registration_security_contract()

    assert contract.role_context_server_derived is True
    assert contract.tenant_context_server_derived is True
    assert contract.client_selected_role_allowed is False
    assert contract.client_selected_plan_allowed is False
    assert MembershipRole.PLATFORM_ADMIN not in contract.invitable_roles
    assert MembershipRole.ORGANIZATION_OWNER not in contract.invitable_roles
    assert contract.invitable_roles == (
        MembershipRole.ORGANIZATION_ADMIN,
        MembershipRole.OPERATOR,
        MembershipRole.AUDITOR,
        MembershipRole.VIEWER,
    )


def test_session_and_password_boundaries_are_explicit() -> None:
    contract = get_identity_registration_security_contract()

    assert contract.password_hash_algorithm == "argon2id"
    assert contract.access_token_storage == "memory"
    assert contract.refresh_token_storage == "http_only_cookie"
    assert contract.session_source_of_truth == "postgresql"
    assert contract.rate_limit_store == "redis"
    assert contract.redis_is_session_authority is False
    assert contract.email_verification_required is True
    assert contract.refresh_token_rotation_required is True
    assert contract.refresh_token_reuse_detection_required is True
    assert contract.csrf_protection_required is True

    assert contract.raw_password_persisted is False
    assert contract.raw_action_token_persisted is False
    assert contract.raw_refresh_token_persisted is False


@pytest.mark.parametrize(
    ("field_name", "unsafe_value"),
    (
        ("platform_admin_public_registration", True),
        ("client_selected_role_allowed", True),
        ("client_selected_plan_allowed", True),
        ("raw_password_persisted", True),
        ("raw_action_token_persisted", True),
        ("raw_refresh_token_persisted", True),
        ("redis_is_session_authority", True),
        ("email_verification_required", False),
        ("refresh_token_rotation_required", False),
        ("refresh_token_reuse_detection_required", False),
        ("csrf_protection_required", False),
        ("tenant_context_server_derived", False),
        ("role_context_server_derived", False),
    ),
)
def test_contract_rejects_weakened_security_flags(
    field_name: str,
    unsafe_value: bool,
) -> None:
    contract = get_identity_registration_security_contract()

    with pytest.raises(ValueError):
        replace(contract, **{field_name: unsafe_value})


def test_contract_rejects_unsafe_role_catalogs() -> None:
    with pytest.raises(ValueError):
        IdentityRegistrationSecurityContract(
            invitable_roles=(MembershipRole.PLATFORM_ADMIN,),
        )

    with pytest.raises(ValueError):
        IdentityRegistrationSecurityContract(
            invitable_roles=(MembershipRole.ORGANIZATION_OWNER,),
        )


def test_account_and_action_lifecycles_are_bounded() -> None:
    assert tuple(AccountStatus) == (
        AccountStatus.PENDING_VERIFICATION,
        AccountStatus.ACTIVE,
        AccountStatus.LOCKED,
        AccountStatus.DISABLED,
        AccountStatus.DELETED,
    )
    assert tuple(AuthActionPurpose) == (
        AuthActionPurpose.VERIFY_EMAIL,
        AuthActionPurpose.RESET_PASSWORD,
        AuthActionPurpose.CHANGE_EMAIL,
        AuthActionPurpose.ACCEPT_INVITATION,
    )


def test_r1_documents_fix_architecture_threats_and_api_boundaries() -> None:
    adr = (
        ROOT
        / "docs"
        / "architecture"
        / "identity-registration-session.adr.md"
    ).read_text(encoding="utf-8")
    threat_model = (
        ROOT
        / "docs"
        / "security"
        / "IDENTITY_REGISTRATION_THREAT_MODEL.md"
    ).read_text(encoding="utf-8")
    api_contracts = (
        ROOT
        / "docs"
        / "api"
        / "IDENTITY_REGISTRATION_CONTRACTS.md"
    ).read_text(encoding="utf-8")

    for marker in (
        "PostgreSQL is authoritative",
        "Argon2id",
        "memory-only",
        "Refresh-token reuse",
        "client_id",
    ):
        assert marker in adr

    for marker in (
        "Account enumeration",
        "Duplicate-email race",
        "Refresh-token replay",
        "Tenant confusion",
        "Redis loss",
    ):
        assert marker in threat_model

    for marker in (
        "POST /auth/register",
        "POST /auth/login",
        "POST /auth/refresh",
        "role, platform_role, membership_role",
        "Unknown fields are rejected",
    ):
        assert marker in api_contracts


def test_registration_contract_module_is_runtime_neutral() -> None:
    source = (
        ROOT
        / "processual_api"
        / "auth"
        / "registration_contracts.py"
    ).read_text(encoding="utf-8")

    forbidden = (
        "APIRouter",
        "include_router",
        "create_async_engine",
        "session.add",
        "send_email",
        "production_allowed=True",
        "raw_password_persisted=True",
    )
    for marker in forbidden:
        assert marker not in source
