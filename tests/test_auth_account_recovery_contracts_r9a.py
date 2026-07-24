from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from processual_api.auth.account_recovery_contracts import (
    AccountRecoveryAuditEventContract,
    AccountRecoveryCompleteRequestContract,
    AccountRecoveryCompleteResponseContract,
    AccountRecoveryFailureCode,
    AccountRecoveryProcessedResponseContract,
    AccountRecoveryPurpose,
    AccountRecoveryRevocationSummaryContract,
    AccountRecoveryStartRequestContract,
    AccountRecoveryStartResponseContract,
    AccountRecoveryState,
    AccountRecoveryVerifyRequestContract,
    AccountRecoveryVerifyResponseContract,
)

NOW = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
RAW_TOKEN = "r" * 64
COMPLETION_TOKEN = "c" * 64
NEW_PASSWORD = "A-strong-recovered-password-2026!"


def test_recovery_purpose_and_states_are_exact() -> None:
    assert tuple(AccountRecoveryPurpose) == (
        AccountRecoveryPurpose.PLATFORM_ACCOUNT_RECOVERY,
    )
    assert tuple(AccountRecoveryState) == (
        AccountRecoveryState.PENDING,
        AccountRecoveryState.VERIFIED,
        AccountRecoveryState.COMPLETED,
        AccountRecoveryState.EXPIRED,
        AccountRecoveryState.REVOKED,
    )


def test_start_response_is_enumeration_resistant() -> None:
    first = AccountRecoveryStartResponseContract()
    second = AccountRecoveryStartResponseContract()

    assert first == second
    assert first.accepted is True
    assert (
        first.message
        == "If the account is eligible, recovery instructions will be sent."
    )
    assert "email" not in first.model_dump()
    assert "user_id" not in first.model_dump()
    assert "recovery_id" not in first.model_dump()


@pytest.mark.parametrize(
    "email",
    [
        "",
        "x",
        "  ",
    ],
)
def test_start_request_rejects_structurally_invalid_identity_input(
    email: str,
) -> None:
    with pytest.raises(ValidationError):
        AccountRecoveryStartRequestContract(email=email)


def test_contracts_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AccountRecoveryStartRequestContract(
            email="owner@example.test",
            role="platform_admin",
        )


def test_verify_request_hides_raw_token_from_repr() -> None:
    request = AccountRecoveryVerifyRequestContract(token=RAW_TOKEN)

    assert RAW_TOKEN not in repr(request)
    assert request.token == RAW_TOKEN


def test_verify_response_grants_no_authenticated_state() -> None:
    response = AccountRecoveryVerifyResponseContract(
        recovery_id=uuid4(),
        state=AccountRecoveryState.VERIFIED,
        completion_token=COMPLETION_TOKEN,
        expires_at=NOW + timedelta(minutes=15),
    )

    assert COMPLETION_TOKEN not in repr(response)
    assert response.access_token_issued is False
    assert response.refresh_token_issued is False
    assert response.session_created is False
    assert response.api_key_issued is False
    assert response.authority_granted is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("access_token_issued", True),
        ("refresh_token_issued", True),
        ("session_created", True),
        ("api_key_issued", True),
        ("authority_granted", True),
    ],
)
def test_verify_response_cannot_claim_authentication_or_authority(
    field: str,
    value: bool,
) -> None:
    payload = {
        "recovery_id": uuid4(),
        "state": AccountRecoveryState.VERIFIED,
        "completion_token": COMPLETION_TOKEN,
        "expires_at": NOW + timedelta(minutes=15),
        field: value,
    }

    with pytest.raises(ValidationError):
        AccountRecoveryVerifyResponseContract(**payload)


def test_complete_request_requires_matching_passwords() -> None:
    with pytest.raises(
        ValidationError,
        match="new_password and confirm_password must match",
    ):
        AccountRecoveryCompleteRequestContract(
            completion_token=COMPLETION_TOKEN,
            new_password=NEW_PASSWORD,
            confirm_password="A-different-recovered-password-2026!",
        )


def test_complete_request_hides_passwords_and_token_from_repr() -> None:
    request = AccountRecoveryCompleteRequestContract(
        completion_token=COMPLETION_TOKEN,
        new_password=NEW_PASSWORD,
        confirm_password=NEW_PASSWORD,
    )

    rendered = repr(request)

    assert COMPLETION_TOKEN not in rendered
    assert NEW_PASSWORD not in rendered


@pytest.mark.parametrize(
    "password",
    [
        "",
        "short",
        "12345678901",
    ],
)
def test_complete_request_rejects_password_below_contract_minimum(
    password: str,
) -> None:
    with pytest.raises(ValidationError):
        AccountRecoveryCompleteRequestContract(
            completion_token=COMPLETION_TOKEN,
            new_password=password,
            confirm_password=password,
        )


def test_completion_requires_mfa_reenrollment_and_no_login() -> None:
    response = AccountRecoveryCompleteResponseContract(
        recovery_id=uuid4(),
        state=AccountRecoveryState.COMPLETED,
        completed_at=NOW,
        revocations=AccountRecoveryRevocationSummaryContract(
            sessions_revoked=2,
            refresh_tokens_revoked=3,
            action_tokens_revoked=4,
            supervisor_session_keys_revoked=1,
            api_keys_revoked=5,
        ),
    )

    assert response.password_changed is True
    assert response.mfa_reenrollment_required is True
    assert response.access_token_issued is False
    assert response.refresh_token_issued is False
    assert response.session_created is False
    assert response.api_key_issued is False
    assert response.authority_granted is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("password_changed", False),
        ("mfa_reenrollment_required", False),
        ("access_token_issued", True),
        ("refresh_token_issued", True),
        ("session_created", True),
        ("api_key_issued", True),
        ("authority_granted", True),
    ],
)
def test_completion_security_invariants_are_not_overridable(
    field: str,
    value: bool,
) -> None:
    payload = {
        "recovery_id": uuid4(),
        "state": AccountRecoveryState.COMPLETED,
        "completed_at": NOW,
        "revocations": {
            "sessions_revoked": 1,
            "refresh_tokens_revoked": 1,
            "action_tokens_revoked": 1,
            "supervisor_session_keys_revoked": 1,
            "api_keys_revoked": 1,
        },
        field: value,
    }

    with pytest.raises(ValidationError):
        AccountRecoveryCompleteResponseContract(**payload)


@pytest.mark.parametrize(
    "field",
    [
        "sessions_revoked",
        "refresh_tokens_revoked",
        "action_tokens_revoked",
        "supervisor_session_keys_revoked",
        "api_keys_revoked",
    ],
)
def test_revocation_counts_cannot_be_negative(field: str) -> None:
    payload = {
        "sessions_revoked": 0,
        "refresh_tokens_revoked": 0,
        "action_tokens_revoked": 0,
        "supervisor_session_keys_revoked": 0,
        "api_keys_revoked": 0,
    }
    payload[field] = -1

    with pytest.raises(ValidationError):
        AccountRecoveryRevocationSummaryContract(**payload)


def test_generic_processed_response_contains_no_sensitive_state() -> None:
    response = AccountRecoveryProcessedResponseContract()

    assert response.model_dump() == {"processed": True}


def test_audit_contract_excludes_secret_bearing_fields() -> None:
    fields = set(AccountRecoveryAuditEventContract.model_fields)

    assert "token" not in fields
    assert "completion_token" not in fields
    assert "password" not in fields
    assert "new_password" not in fields
    assert "confirm_password" not in fields
    assert "recovery_email" not in fields
    assert "ip_address" not in fields
    assert "user_agent" not in fields
    assert "access_token" not in fields
    assert "refresh_token" not in fields
    assert "api_key" not in fields


def test_audit_event_supports_safe_failure_classification() -> None:
    event = AccountRecoveryAuditEventContract(
        event_id=uuid4(),
        recovery_id=None,
        user_id=None,
        action="verify",
        result="processed",
        occurred_at=NOW,
        failure_code=AccountRecoveryFailureCode.INVALID_OR_EXPIRED,
    )

    payload = event.model_dump(mode="json")

    assert payload["failure_code"] == "invalid_or_expired"
    assert "token" not in payload
    assert "email" not in payload


def test_public_exports_cover_contract_surface() -> None:
    import processual_api.auth.account_recovery_contracts as contracts

    expected = {
        "AccountRecoveryAuditEventContract",
        "AccountRecoveryCompleteRequestContract",
        "AccountRecoveryCompleteResponseContract",
        "AccountRecoveryFailureCode",
        "AccountRecoveryPassword",
        "AccountRecoveryProcessedResponseContract",
        "AccountRecoveryPurpose",
        "AccountRecoveryRevocationSummaryContract",
        "AccountRecoveryStartRequestContract",
        "AccountRecoveryStartResponseContract",
        "AccountRecoveryState",
        "AccountRecoveryToken",
        "AccountRecoveryVerifyRequestContract",
        "AccountRecoveryVerifyResponseContract",
    }

    assert set(contracts.__all__) == expected


def test_contract_module_contains_no_runtime_side_effect_imports() -> None:
    from pathlib import Path

    source = Path(
        "processual_api/auth/account_recovery_contracts.py"
    ).read_text(encoding="utf-8").lower()

    forbidden = (
        "sqlalchemy",
        "redis",
        "httpx",
        "requests",
        "socket",
        "subprocess",
        "sessionmaker",
        "create_async_engine",
        "backgroundtasks",
    )

    for marker in forbidden:
        assert marker not in source
